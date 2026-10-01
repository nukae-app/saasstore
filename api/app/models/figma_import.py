"""Integració amb Figma per importar dissenys al storefront constructible
(ver docs/ARQUITECTURA_DISENY_FIGMA.md). El token OAuth mai viu aquí: va a
`tenant_secrets.py` (`TenantSecrets.figma_access_token`/`figma_refresh_token`,
AWS Secrets Manager), mateix patró que `discogs_token` — aquestes taules
només guarden metadades no sensibles i el registre d'imports."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ._base import TenantScoped, _uuid


class FigmaConnection(TenantScoped, Base):
    """Metadades no sensibles de la connexió Figma del tenant (per mostrar
    "Connectat com a..." a l'admin sense llegir el secret). Una connexió per
    tenant en v1 — l'autoservei és el tenant sencer connectant el seu propi
    compte, no cada usuari admin per separat (mateix criteri que
    `discogs_token`, no com `SpotifyConnection`, que és per usuari client)."""

    __tablename__ = "figma_connections"
    __table_args__ = (UniqueConstraint("tenant_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    figma_user_id: Mapped[str] = mapped_column(String(100))
    figma_handle: Mapped[str | None] = mapped_column(String(200))
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FigmaImportStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    error = "error"


class FigmaImportJob(TenantScoped, Base):
    """Cua d'importació d'un fitxer Figma cap a un `Page` — mateix patró que
    `DespesaImport` (cua de revisió PDF-OCR): el resultat és sempre un
    ESBORRANY (`result_tree`), mai s'escriu directe a `Page.published_tree`.

    `raw_snapshot_path` és un punter a `/uploads` (mateix mecanisme que
    `ReleaseImage`), NUNCA el JSON cru de Figma inline a Postgres — un
    fitxer complex pot pesar diversos MB i aquí mai cal filtrar/indexar pel
    contingut, només consultar-lo puntualment per depurar un import."""

    __tablename__ = "figma_import_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    figma_file_key: Mapped[str] = mapped_column(String(200))
    # Frame concret del fitxer a importar (l'admin l'ha de triar explícitament
    # — ver routers/figma.py::list_frames — mai s'infereix sol un frame per
    # defecte). Migració f60f71b05e91, afegida en Fase 4.
    figma_node_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[FigmaImportStatus] = mapped_column(
        Enum(FigmaImportStatus, name="figma_import_status"),
        default=FigmaImportStatus.pending, server_default="pending", index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    raw_snapshot_path: Mapped[str | None] = mapped_column(String(500))
    # {"tree": {id,type,props,style,children}, "warnings": [str, ...]} —
    # `tree` sigue el formato portable de `Page.draft_tree` (§3); `warnings`
    # son los nodos que no se pudieron mapear (frames sin auto-layout, tipos
    # sin soporte — ver services/figma.py::map_node_to_tree, §6 "no s'intenta
    # resoldre amb heurístiques fràgils").
    result_tree: Mapped[dict | None] = mapped_column(JSON)
    target_page_id: Mapped[int | None] = mapped_column(ForeignKey("pages.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    target_page: Mapped["Page | None"] = relationship()
