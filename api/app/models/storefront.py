from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from ._base import TenantScoped


class Page(TenantScoped, Base):
    """Página constructible del storefront del tenant (home, "sobre
    nosaltres", landings pròpies...) — ver docs/ARQUITECTURA_DISENY_FIGMA.md
    §3. Substitueix conceptualment `HomeBlock` (llista plana de blocs, només
    per al home) per un arbre de nodes genèric que admet qualsevol pàgina.
    Conviu amb `HomeBlock` fins que la Fase 5 d'aquell document migri els
    tenants existents i el retiri — no s'ha tocat `HomeBlock` en aquest pas.

    L'arbre sencer viu com un únic JSON per versió, mai files per node:
    sempre es carrega/desa la pàgina completa per editar o renderitzar,
    mateix criteri que `ConfiguracioBotiga.theme` o `Release.tracklist`.
    Publicar és copiar `draft_tree` -> `published_tree` explícitament —
    mai automàtic. Sense taula d'historial de versions en v1 (decisió
    §3 del document): es publica direct sobre l'única versió publicada.

    Naming en anglès (`slug`, `draft_tree`...): és taula nova, segueix el
    canon fixat a ARQUITECTURA_CORE_VERTICAL.md §3, no l'espanyol/català
    de les taules anteriors a aquella decisió."""

    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("tenant_id", "slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), index=True)
    draft_tree: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    published_tree: Mapped[dict | None] = mapped_column(JSON)
    # Tipus de text {ca,es,en} (ver docs/PLAN_MULTIIDIOMA_CONTINGUT.md) — el
    # nou sistema neix ja multi-idioma, no arrossega el defecte de
    # `HomeBlock.props` (string pla, un sol idioma).
    seo_title: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    seo_description: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    # Tipus de node que han d'existir a l'arbre perquè es pugui publicar
    # (docs/ARQUITECTURA_DISENY_FIGMA.md §3d) — buida per a qualsevol pàgina
    # normal. Només te sentit amb valors de `PROTECTED_NODE_TYPES`
    # (schemas/storefront.py), validat allà, no aquí: aquesta columna només
    # emmagatzema la llista, `publish_page` (routers/pages.py) és qui la fa
    # complir de veritat contra `draft_tree` en publicar.
    requires_nodes: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class HomeBlock(TenantScoped, Base):
    """Un bloc del home públic del tenant, en l'ordre en què es renderitza.
    Substitueix la seqüència fixa que abans hi havia hardcoded a
    web/app/[locale]/page.jsx (hero, novetats, curador...) per una llista
    per tenant que l'admin pot afegir/reordenar/apagar des del constructor.

    `block_type` es valida contra `api/app/blocks/registry.py` (un schema
    Pydantic fix per tipus), mateix criteri que `Tenant.vertical_id`: el
    vocabulari vàlid viu en codi, no en un constraint de BD. `props` només
    guarda copy/comportament configurable (títol, subtítol, quina etiqueta
    alimenta un carrusel...) — mai dades de catàleg en viu (releases,
    stock): això sempre el resol `page.jsx` en cada request, igual que avui.

    Sense columna `page` en v1 — només existeix una pàgina "construïble",
    el home. Afegir-la el dia que calgui una segona és una migració trivial."""

    __tablename__ = "home_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    block_type: Mapped[str] = mapped_column(String(60), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    props: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UploadedVideo(TenantScoped, Base):
    """Vídeo pujat per l'admin per fer-lo servir en blocs (avui només
    Hero/background_video, ver blocks/registry.py::HeroProps). Registre
    petit i genèric — no lligat a cap block_id — perquè el mateix vídeo es
    pugui reutilitzar en blocs diferents i l'admin el pugui triar d'una
    petita galeria en lloc de tornar-lo a pujar cada cop (ver
    routers/home_blocks.py: upload-video / videos)."""

    __tablename__ = "uploaded_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(500))
    filename: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
