import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Address, User
from ...services.security import get_current_user

router = APIRouter(prefix="/me", tags=["me"])


class AddressIn(BaseModel):
    recipient_name: str
    address_line1: str
    address_line2: str | None = None
    city: str
    postal_code: str
    province: str | None = None
    country: str = "ES"
    phone: str | None = None
    is_default: bool = False


class AddressOut(BaseModel):
    id: uuid.UUID
    recipient_name: str
    address_line1: str
    address_line2: str | None
    city: str
    postal_code: str
    province: str | None
    country: str
    phone: str | None
    is_default: bool

    model_config = {"from_attributes": True}


@router.get("/addresses", response_model=list[AddressOut])
def list_addresses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Address)
        .where(Address.user_id == user.id)
        .order_by(Address.is_default.desc(), Address.id)
    ).all()


@router.post("/addresses", response_model=AddressOut, status_code=201)
def create_address(
    payload: AddressIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.is_default:
        db.execute(
            Address.__table__.update()
            .where(Address.user_id == user.id)
            .values(is_default=False)
        )
    addr = Address(user_id=user.id, **payload.model_dump())
    db.add(addr)
    db.commit()
    db.refresh(addr)
    return addr


@router.put("/addresses/{addr_id}", response_model=AddressOut)
def update_address(
    addr_id: uuid.UUID,
    payload: AddressIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    addr = db.scalar(select(Address).where(Address.id == addr_id, Address.user_id == user.id))
    if addr is None:
        raise HTTPException(404, "Adreça no trobada")
    if payload.is_default and not addr.is_default:
        db.execute(
            Address.__table__.update()
            .where(Address.user_id == user.id)
            .values(is_default=False)
        )
    for field, val in payload.model_dump().items():
        setattr(addr, field, val)
    db.commit()
    db.refresh(addr)
    return addr


@router.delete("/addresses/{addr_id}", status_code=204)
def delete_address(
    addr_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    addr = db.scalar(select(Address).where(Address.id == addr_id, Address.user_id == user.id))
    if addr is None:
        raise HTTPException(404, "Adreça no trobada")
    db.delete(addr)
    db.commit()


@router.post("/addresses/{addr_id}/set-default", response_model=AddressOut)
def set_default_address(
    addr_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.execute(
        Address.__table__.update()
        .where(Address.user_id == user.id)
        .values(is_default=False)
    )
    addr = db.scalar(select(Address).where(Address.id == addr_id, Address.user_id == user.id))
    if addr is None:
        raise HTTPException(404, "Adreça no trobada")
    addr.is_default = True
    db.commit()
    db.refresh(addr)
    return addr
