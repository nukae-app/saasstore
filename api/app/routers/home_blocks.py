"""Bloques del home constructible del tenant (ver models/storefront.py::HomeBlock
i blocks/registry.py). El listado admin devuelve todo (activos e inactivos);
el público solo lo `enabled=True`, sin autenticación, para que
[locale]/page.jsx lo pueda pedir en cada request igual que /config/public."""

import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..blocks.registry import BLOCK_REGISTRY
from ..database import get_db
from ..models import HomeBlock
from ..schemas import HomeBlockCreateIn, HomeBlockOut, HomeBlockPublicOut, HomeBlockReorderIn, HomeBlockUpdateIn
from ..services.security import require_admin

router = APIRouter(prefix="/admin/home-blocks", tags=["home-blocks"], dependencies=[Depends(require_admin)])
public_router = APIRouter(prefix="/config/public/home-blocks", tags=["home-blocks"])

# Mateix volum compartit amb Caddy que favicon/logo (ver routers/configuracio.py)
UPLOADS_DIR = "/app/uploads"
ALLOWED_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")


@router.post("/upload-background")
async def upload_background_image(file: UploadFile = File(...)):
    # Sense lligar a cap block_id: un bloc nou encara no existeix al
    # servidor mentre és a l'esborrany de l'admin (ver disseny-web/page.jsx),
    # així que aquest endpoint només desa el fitxer i retorna la URL — és
    # l'admin qui la desa dins de `props.background_image_url` en prémer
    # "Guardar canvis", igual que qualsevol altre camp del formulari.
    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        raise HTTPException(422, "Només s'accepten imatges PNG, JPG o WebP")
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    filename = f"{uuid.uuid4()}{ext}"
    content = await file.read()
    with open(os.path.join(UPLOADS_DIR, filename), "wb") as f:
        f.write(content)
    return {"url": f"/uploads/{filename}"}


def _validate_props(block_type: str, props: dict) -> dict:
    schema = BLOCK_REGISTRY.get(block_type)
    if schema is None:
        raise HTTPException(422, f"Tipus de bloc desconegut: '{block_type}'")
    try:
        validated = schema.model_validate(props)
    except Exception as exc:
        raise HTTPException(422, f"Props no vàlides per '{block_type}': {exc}") from exc
    return validated.model_dump()


@router.get("", response_model=list[HomeBlockOut])
def list_home_blocks(db: Session = Depends(get_db)):
    return db.scalars(select(HomeBlock).order_by(HomeBlock.position)).all()


@router.post("", response_model=HomeBlockOut, status_code=201)
def create_home_block(payload: HomeBlockCreateIn, db: Session = Depends(get_db)):
    props = _validate_props(payload.block_type, payload.props)
    last_position = db.scalar(select(HomeBlock.position).order_by(HomeBlock.position.desc()).limit(1))
    block = HomeBlock(block_type=payload.block_type, props=props, position=(last_position or 0) + 1)
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


@router.patch("/reorder", response_model=list[HomeBlockOut])
def reorder_home_blocks(payload: HomeBlockReorderIn, db: Session = Depends(get_db)):
    # Bulk: una tirada d'arrossegar-i-deixar anar produeix l'ordre sencer
    # d'un cop, mateix patró que admin_reorder_pagines (admin/pagines.py).
    for item in payload.order:
        block = db.get(HomeBlock, item.id)
        if block is not None:
            block.position = item.position
    db.commit()
    return db.scalars(select(HomeBlock).order_by(HomeBlock.position)).all()


def _get_block_or_404(block_id: int, db: Session) -> HomeBlock:
    block = db.get(HomeBlock, block_id)
    if block is None:
        raise HTTPException(404, "Bloc no trobat")
    return block


@router.patch("/{block_id}", response_model=HomeBlockOut)
def update_home_block(block_id: int, payload: HomeBlockUpdateIn, db: Session = Depends(get_db)):
    block = _get_block_or_404(block_id, db)
    if payload.props is not None:
        block.props = _validate_props(block.block_type, payload.props)
    if payload.enabled is not None:
        block.enabled = payload.enabled
    db.commit()
    db.refresh(block)
    return block


@router.delete("/{block_id}", status_code=204)
def delete_home_block(block_id: int, db: Session = Depends(get_db)):
    block = _get_block_or_404(block_id, db)
    db.delete(block)
    db.commit()


@public_router.get("", response_model=list[HomeBlockPublicOut])
def list_public_home_blocks(db: Session = Depends(get_db)):
    return db.scalars(
        select(HomeBlock).where(HomeBlock.enabled.is_(True)).order_by(HomeBlock.position)
    ).all()
