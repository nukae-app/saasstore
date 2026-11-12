import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Release, ReleaseImage
from ...schemas import ReleaseImageOut
from ...services.security import require_admin
from ...services.storage import get_storage
from ...services.uploads import validate_image_bytes

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

@router.get("/releases/{release_id}/images", response_model=list[ReleaseImageOut])
def get_release_images(release_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.scalars(
        select(ReleaseImage)
        .where(ReleaseImage.release_id == release_id)
        .order_by(ReleaseImage.position)
    ).all()


@router.post("/releases/{release_id}/images", response_model=ReleaseImageOut, status_code=201)
async def upload_release_image(
    release_id: uuid.UUID,
    file: UploadFile = File(...),
    tipus: str = "altre",
    db: Session = Depends(get_db),
):
    if not db.get(Release, release_id):
        raise HTTPException(404, "Release no trobat")

    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        raise HTTPException(422, "Només s'accepten imatges JPG, PNG o WebP")

    content = await file.read()
    validate_image_bytes(content, ext, (".jpg", ".jpeg", ".png", ".webp"))
    filename = f"{uuid.uuid4()}{ext}"
    get_storage().save(filename, content)

    posicio = (db.scalar(
        select(ReleaseImage.position)
        .where(ReleaseImage.release_id == release_id)
        .order_by(ReleaseImage.position.desc())
        .limit(1)
    ) or 0) + 1

    img = ReleaseImage(
        release_id=release_id,
        url=f"/uploads/{filename}",
        position=posicio,
        type=tipus,
        source="upload",
    )
    db.add(img)
    db.commit()
    db.refresh(img)
    return img


@router.delete("/releases/{release_id}/images/{image_id}", status_code=204)
def delete_release_image(release_id: uuid.UUID, image_id: int, db: Session = Depends(get_db)):
    img = db.scalar(
        select(ReleaseImage).where(
            ReleaseImage.id == image_id, ReleaseImage.release_id == release_id
        )
    )
    if img is None:
        raise HTTPException(404, "Imatge no trobada")
    # Elimina el fitxer local si és un upload
    if img.source == "upload" and img.url.startswith("/uploads/"):
        get_storage().delete(os.path.basename(img.url))
    db.delete(img)
    db.commit()


@router.patch("/releases/{release_id}/images/{image_id}/posicio")
def reorder_release_image(release_id: uuid.UUID, image_id: int, posicio: int, db: Session = Depends(get_db)):
    img = db.scalar(
        select(ReleaseImage).where(
            ReleaseImage.id == image_id, ReleaseImage.release_id == release_id
        )
    )
    if img is None:
        raise HTTPException(404, "Imatge no trobada")
    img.position = posicio
    db.commit()
    return {"id": img.id, "posicio": img.position}
