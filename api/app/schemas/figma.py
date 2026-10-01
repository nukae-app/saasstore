import uuid
from datetime import datetime

from pydantic import BaseModel


class FigmaConnectionOut(BaseModel):
    connected: bool
    figma_handle: str | None = None
    connected_at: datetime | None = None


class FigmaStylesRequestIn(BaseModel):
    file_key: str


class FigmaStyleOut(BaseModel):
    """Un estil de color/tipografia trobat al fitxer, amb el valor ja
    resolt (ver services/figma.py) — el frontend el mostra perquè l'admin
    triï manualment a quin camp de `ThemeTokens` correspon (mai un mapeig
    automàtic per nom, ver docstring de get_file_design_styles)."""
    figma_style_id: str
    name: str
    kind: str  # "color" | "text"
    value: str


class FigmaFrameOut(BaseModel):
    """Fase 4 — un frame de primer nivell que l'admin pot triar per
    importar. `has_auto_layout=False` es mostra igualment (ver
    services/figma.py::list_top_level_frames): l'error real surt en intentar
    importar-lo, no abans."""
    id: str
    name: str
    page: str
    has_auto_layout: bool


class FigmaImportJobCreateIn(BaseModel):
    file_key: str
    node_id: str


class FigmaImportJobOut(BaseModel):
    id: uuid.UUID
    status: str
    error_message: str | None = None
    tree: dict | None = None
    warnings: list[str] = []
    target_page_id: int | None = None

    model_config = {"from_attributes": True}


class FigmaImportApplyIn(BaseModel):
    target_page_id: int
