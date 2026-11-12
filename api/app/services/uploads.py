"""Validación común de imágenes subidas desde el admin (hoy solo la sube un
admin, pero el fichero se sirve tal cual desde /uploads en el dominio público:
no nos fiamos de la extensión que declara el cliente)."""

import io
import os

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB: sobra para fotos de carátula/banner

# Formato real detectado por Pillow -> extensiones con las que se acepta.
_EXTS_BY_FORMAT = {
    "JPEG": {".jpg", ".jpeg"},
    "PNG": {".png"},
    "WEBP": {".webp"},
    "GIF": {".gif"},
    "ICO": {".ico"},
}


def validate_image_bytes(content: bytes, ext: str, allowed_exts: tuple[str, ...]) -> None:
    """Lanza 422 si `ext` no está permitida, el fichero pesa demasiado, no es
    una imagen real o su formato real no corresponde a la extensión (p. ej. un
    HTML renombrado a .png)."""
    ext = ext.lower()
    if ext not in allowed_exts:
        raise HTTPException(422, "Format d'imatge no permès")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(422, "La imatge pesa massa (màxim 10 MB)")
    try:
        with Image.open(io.BytesIO(content)) as img:
            fmt = img.format
            img.verify()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise HTTPException(422, "El fitxer no és una imatge vàlida")
    if ext not in _EXTS_BY_FORMAT.get(fmt or "", set()):
        raise HTTPException(422, "El contingut no coincideix amb l'extensió del fitxer")


def ext_of(filename: str | None) -> str:
    return os.path.splitext(filename or "")[-1].lower()
