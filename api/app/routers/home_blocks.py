"""Bloques del home constructible del tenant (ver models/storefront.py::HomeBlock
i blocks/registry.py). El listado admin devuelve todo (activos e inactivos);
el público solo lo `enabled=True`, sin autenticación, para que
[locale]/page.jsx lo pueda pedir en cada request igual que /config/public."""

import os
import subprocess
import tempfile
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..blocks.registry import BLOCK_REGISTRY
from ..database import get_db
from ..models import HomeBlock, UploadedVideo
from ..schemas import (
    HomeBlockCreateIn,
    HomeBlockOut,
    HomeBlockPublicOut,
    HomeBlockReorderIn,
    HomeBlockUpdateIn,
    UploadedVideoOut,
)
from ..services.security import require_admin
from ..services.video import VideoTooLongError, transcode_for_web

router = APIRouter(prefix="/admin/home-blocks", tags=["home-blocks"], dependencies=[Depends(require_admin)])
public_router = APIRouter(prefix="/config/public/home-blocks", tags=["home-blocks"])

# Mateix volum compartit amb Caddy que favicon/logo (ver routers/configuracio.py)
UPLOADS_DIR = "/app/uploads"
ALLOWED_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")
ALLOWED_VIDEO_EXTS = (".mp4", ".webm", ".mov", ".mkv", ".avi")
# Cap del fitxer ORIGINAL abans de recomprimir (ver services/video.py) — el
# resultat final sempre pesa ~3MB independentment d'això, aquest límit
# només evita perdre temps de CPU recomprimint un fitxer descomunal.
MAX_UPLOAD_SIZE_BYTES = 300 * 1024 * 1024


def _remove_if_exists(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


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


@router.post("/upload-video", response_model=UploadedVideoOut, status_code=201)
async def upload_video(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # A diferència de "upload-background", aquest SÍ queda registrat (taula
    # `uploaded_videos`, ver models/storefront.py) perquè l'admin el pugui
    # tornar a triar més tard des de la mini biblioteca (GET /videos) sense
    # haver-lo de tornar a pujar — un vídeo de fons pesa massa per repetir
    # la pujada cada cop que es reutilitza en un altre bloc/tenant.
    #
    # L'original NO es guarda mai: es recomprimeix sempre (ver
    # services/video.py) perquè el pes final sigui petit i constant
    # independentment del que pugi l'admin — no hi ha CDN al davant
    # d'aquest servidor i cada tenant pot tenir el seu propi domini, així
    # que la mida del fitxer és l'única palanca de cost real disponible.
    original_name = file.filename or "video"
    ext = os.path.splitext(original_name)[-1].lower()
    if ext not in ALLOWED_VIDEO_EXTS:
        raise HTTPException(422, "Format de vídeo no reconegut")
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(422, "El vídeo original pesa massa")

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_in:
        tmp_in.write(content)
        tmp_in_path = tmp_in.name

    filename = f"{uuid.uuid4()}.mp4"
    out_path = os.path.join(UPLOADS_DIR, filename)
    try:
        transcode_for_web(tmp_in_path, out_path)
    except VideoTooLongError as exc:
        _remove_if_exists(out_path)
        raise HTTPException(422, str(exc)) from exc
    except subprocess.CalledProcessError as exc:
        _remove_if_exists(out_path)
        raise HTTPException(422, "No s'ha pogut processar el vídeo") from exc
    finally:
        os.remove(tmp_in_path)

    video = UploadedVideo(url=f"/uploads/{filename}", filename=original_name, size_bytes=os.path.getsize(out_path))
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


@router.get("/videos", response_model=list[UploadedVideoOut])
def list_uploaded_videos(db: Session = Depends(get_db)):
    return db.scalars(select(UploadedVideo).order_by(UploadedVideo.created_at.desc())).all()


@router.delete("/videos/{video_id}", status_code=204)
def delete_uploaded_video(video_id: int, db: Session = Depends(get_db)):
    video = db.get(UploadedVideo, video_id)
    if video is None:
        raise HTTPException(404, "Vídeo no trobat")
    _remove_if_exists(os.path.join(UPLOADS_DIR, os.path.basename(video.url)))
    db.delete(video)
    db.commit()


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
