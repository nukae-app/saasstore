from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Proveedor
from ...schemas import ProveedorIn, ProveedorOut
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["erp"], dependencies=[Depends(require_admin)])


@router.post("/proveedores", status_code=201, response_model=ProveedorOut)
def create_proveedor(payload: ProveedorIn, db: Session = Depends(get_db)):
    proveedor = Proveedor(**payload.model_dump())
    db.add(proveedor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Ya existe un proveedor con el nombre '{payload.name}'")
    db.refresh(proveedor)
    return proveedor


@router.get("/proveedores", response_model=list[ProveedorOut])
def list_proveedores(db: Session = Depends(get_db)):
    return db.scalars(select(Proveedor).order_by(Proveedor.name)).all()


# Nota: GET/PATCH d'un proveïdor individual ja existeixen a comptabilitat.py
