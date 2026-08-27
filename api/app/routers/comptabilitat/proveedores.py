import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Proveedor
from ...schemas import ProveedorIn, ProveedorOut
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["comptabilitat"], dependencies=[Depends(require_admin)])

# Nota: CREATE ja és a erp.py — aquí només GET/PATCH individual.


@router.patch("/proveedores/{prov_id}", response_model=ProveedorOut)
def update_proveidor(prov_id: uuid.UUID, payload: ProveedorIn, db: Session = Depends(get_db)):
    prov = db.get(Proveedor, prov_id)
    if prov is None:
        raise HTTPException(404, "Proveïdor no trobat")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(prov, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Ja existeix un proveïdor amb el nom '{payload.name}'")
    db.refresh(prov)
    return prov


@router.get("/proveedores/{prov_id}", response_model=ProveedorOut)
def get_proveidor(prov_id: uuid.UUID, db: Session = Depends(get_db)):
    prov = db.get(Proveedor, prov_id)
    if prov is None:
        raise HTTPException(404, "Proveïdor no trobat")
    return prov
