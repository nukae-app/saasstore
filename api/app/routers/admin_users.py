"""Gestió d'usuaris per al panell d'administració."""

import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Compra, Item, Order, OrderItem, User, VentaExterna
from ..services.security import hash_password, require_admin

router = APIRouter(prefix="/admin/users", tags=["admin-users"], dependencies=[Depends(require_admin)])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class UserCreateIn(BaseModel):
    email: str
    name: str | None = None
    phone: str | None = None
    role: str = "cliente"
    active: bool = True
    consent_newsletter: bool = False
    language: str = "ca"
    internal_notes: str | None = None


class UserPatchIn(BaseModel):
    name: str | None = None
    phone: str | None = None
    active: bool | None = None
    role: str | None = None
    consent_newsletter: bool | None = None
    language: str | None = None
    internal_notes: str | None = None


class SetPasswordIn(BaseModel):
    password: str


def _user_dict(u: User, providers: list[str]) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "phone": u.phone,
        "role": u.role,
        "active": u.active,
        "consent_newsletter": u.consent_newsletter,
        "language": u.language,
        "internal_notes": u.internal_notes,
        "providers": providers,
        "created_at": u.created_at,
    }


# ---------------------------------------------------------------------------
# Stats globals
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(User.id)))
    actius = db.scalar(select(func.count(User.id)).where(User.active == True))
    newsletter = db.scalar(
        select(func.count(User.id)).where(User.active == True, User.consent_newsletter == True)
    )
    admins = db.scalar(select(func.count(User.id)).where(User.role == "admin", User.active == True))
    return {
        "total": total,
        "actius": actius,
        "inactius": total - actius,
        "newsletter": newsletter,
        "admins": admins,
    }


# ---------------------------------------------------------------------------
# Cercador lleuger (per als selectors de TPV i Compres)
# ---------------------------------------------------------------------------

@router.get("/search")
def search_users(q: str = Query(min_length=2), db: Session = Depends(get_db)):
    ql = f"%{q.lower()}%"
    users = db.scalars(
        select(User)
        .where(
            User.active == True,
            User.email.ilike(ql) | User.name.ilike(ql) | User.phone.ilike(ql),
        )
        .order_by(User.name)
        .limit(10)
    ).all()
    return [{"id": u.id, "name": u.name, "email": u.email, "phone": u.phone} for u in users]


# ---------------------------------------------------------------------------
# Export CSV newsletter
# ---------------------------------------------------------------------------

@router.get("/export/newsletter")
def export_newsletter(db: Session = Depends(get_db)):
    users = db.scalars(
        select(User)
        .where(User.active == True, User.consent_newsletter == True)
        .order_by(User.created_at.desc())
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["email", "nombre", "telefon", "idioma", "alta"])
    for u in users:
        writer.writerow([
            u.email,
            u.name or "",
            u.phone or "",
            u.language,
            u.created_at.strftime("%Y-%m-%d") if u.created_at else "",
        ])
    output.seek(0)
    filename = f"newsletter_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---------------------------------------------------------------------------
# Llistat
# ---------------------------------------------------------------------------

SORTABLE_COLUMNS = {
    "nombre": User.name,
    "rol": User.role,
    "consent_newsletter": User.consent_newsletter,
    "activo": User.active,
    "created_at": User.created_at,
}


@router.get("")
def list_users(
    q: str | None = None,
    activo: bool | None = None,
    newsletter: bool | None = None,
    rol: str | None = None,
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    order_by: str | None = None,
    order_dir: str = "desc",
    db: Session = Depends(get_db),
):
    sort_col = SORTABLE_COLUMNS.get(order_by, User.created_at)
    stmt = select(User).options(selectinload(User.identities)).order_by(
        sort_col.desc() if order_dir == "desc" else sort_col.asc()
    )
    if activo is not None:
        stmt = stmt.where(User.active == activo)
    if newsletter is not None:
        stmt = stmt.where(User.consent_newsletter == newsletter)
    if rol:
        stmt = stmt.where(User.role == rol)
    if q:
        ql = f"%{q.lower()}%"
        stmt = stmt.where(
            User.email.ilike(ql) | User.name.ilike(ql) | User.phone.ilike(ql)
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    users = db.scalars(stmt.offset(skip).limit(limit)).all()

    user_ids = [u.id for u in users]

    orders_by_user = dict(db.execute(
        select(Order.user_id, func.count(Order.id))
        .where(Order.user_id.in_(user_ids))
        .group_by(Order.user_id)
    ).all())

    vendes_by_user = dict(db.execute(
        select(VentaExterna.user_id, func.count(VentaExterna.id))
        .where(VentaExterna.user_id.in_(user_ids))
        .group_by(VentaExterna.user_id)
    ).all())

    compres_by_user = dict(db.execute(
        select(Compra.user_id, func.count(Compra.id))
        .where(Compra.user_id.in_(user_ids))
        .group_by(Compra.user_id)
    ).all())

    result = []
    for u in users:
        providers = [i.provider for i in u.identities]
        d = _user_dict(u, providers)
        d["stats"] = {
            "orders": orders_by_user.get(u.id, 0),
            "vendes_tpv": vendes_by_user.get(u.id, 0),
            "compres_records": compres_by_user.get(u.id, 0),
        }
        result.append(d)

    return {"total": total, "items": result}


# ---------------------------------------------------------------------------
# Crear usuari
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def create_user(payload: UserCreateIn, db: Session = Depends(get_db)):
    u = User(
        email=payload.email.lower().strip(),
        name=payload.name,
        phone=payload.phone,
        role=payload.role,
        active=payload.active,
        consent_newsletter=payload.consent_newsletter,
        language=payload.language,
        internal_notes=payload.internal_notes,
    )
    db.add(u)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Ja existeix un usuari amb l'email '{payload.email}'")
    db.refresh(u)
    return _user_dict(u, [])


# ---------------------------------------------------------------------------
# Assignar contrasenya (accés per email+contrasenya, sense passar per l'usuari)
# ---------------------------------------------------------------------------

@router.post("/{user_id}/set-password", status_code=204)
def admin_set_password(user_id: uuid.UUID, payload: SetPasswordIn, db: Session = Depends(get_db)):
    if len(payload.password) < 8:
        raise HTTPException(422, "La contrasenya ha de tenir mínim 8 caràcters")
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "Usuari no trobat")
    u.password_hash = hash_password(payload.password)
    db.commit()


# ---------------------------------------------------------------------------
# Detall
# ---------------------------------------------------------------------------

@router.get("/{user_id}")
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db)):
    u = db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.identities), selectinload(User.addresses))
    )
    if u is None:
        raise HTTPException(404, "Usuari no trobat")

    providers = [i.provider for i in u.identities]
    d = _user_dict(u, providers)
    d["addresses"] = [
        {"id": a.id, "address_line1": a.address_line1, "city": a.city, "postal_code": a.postal_code, "country": a.country}
        for a in u.addresses
    ]

    orders = db.scalars(
        select(Order)
        .where(Order.user_id == user_id)
        .options(selectinload(Order.items).selectinload(OrderItem.item).selectinload(Item.release))
        .order_by(Order.created_at.desc())
    ).all()
    d["orders"] = [
        {
            "id": o.id,
            "status": o.status,
            "total": float(o.total),
            "created_at": o.created_at,
            "items": [
                {"artista": oi.item.release.artista, "titulo": oi.item.release.title, "precio": float(oi.price)}
                for oi in o.items if oi.item and oi.item.release
            ],
        }
        for o in orders
    ]

    vendes = db.scalars(
        select(VentaExterna)
        .where(VentaExterna.user_id == user_id)
        .options(selectinload(VentaExterna.item).selectinload(Item.release))
        .order_by(VentaExterna.date.desc())
    ).all()
    d["vendes_tpv"] = [
        {
            "id": v.id,
            "artista": v.item.release.artista if v.item and v.item.release else None,
            "titulo": v.item.release.title if v.item and v.item.release else None,
            "description": v.description,
            "channel": v.channel,
            "payment_method": v.payment_method,
            "sale_price": float(v.sale_price),
            "date": v.date,
        }
        for v in vendes
    ]

    compres = db.scalars(
        select(Compra)
        .where(Compra.user_id == user_id)
        .options(selectinload(Compra.items).selectinload(Item.release))
        .order_by(Compra.date.desc())
    ).all()
    d["compres_records"] = [
        {
            "id": c.id,
            "fecha": c.date,
            "num_items": len(c.items),
            "total_pagat": float(sum(it.acquisition_cost or 0 for it in c.items)),
            "items": [
                {
                    "artista": it.release.artista if it.release else None,
                    "titulo": it.release.title if it.release else None,
                    "coste": float(it.acquisition_cost or 0),
                }
                for it in c.items if it.release
            ],
        }
        for c in compres
    ]

    return d


# ---------------------------------------------------------------------------
# Editar
# ---------------------------------------------------------------------------

@router.patch("/{user_id}")
def update_user(user_id: uuid.UUID, payload: UserPatchIn, db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "Usuari no trobat")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(u, field, val)
    db.commit()
    db.refresh(u)
    providers = [i.provider for i in u.identities]
    return _user_dict(u, providers)


# ---------------------------------------------------------------------------
# Anonimitzar (RGPD) — conserva pedidos per obligació fiscal
# ---------------------------------------------------------------------------

@router.post("/{user_id}/anonymize")
def anonymize_user(user_id: uuid.UUID, db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "Usuari no trobat")
    anon_id = str(uuid.uuid4()).replace("-", "")[:12]
    u.email = f"anon-{anon_id}@deleted.local"
    u.name = None
    u.phone = None
    u.internal_notes = None
    u.active = False
    u.consent_newsletter = False
    db.commit()
    return {"ok": True, "email": u.email}
