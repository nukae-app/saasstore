"""Import estructural de Figma (Fase 4, docs/ARQUITECTURA_DISENY_FIGMA.md
§4) — encolat des de `routers/figma.py::create_import_job`. Llegir un
fitxer Figma sencer i exportar imatges no pot ser síncron dins d'un
request (§2 del document), d'aquí Celery.

`FigmaImportJob` és `TenantScoped` amb RLS — aquesta tasca obre la seva
pròpia sessió (`SessionLocal()`, no hi ha request) i ha d'envoltar TOTA
consulta amb `scoped_to(db, tenant_id)`, mateix criteri que
`tasks/subscripcions.py`. Sense això, la consulta no veuria el job que
acaba de crear el request original."""

import os
import uuid

import httpx

from ..celery_app import celery_app
from ..database import SessionLocal
from ..models import FigmaImportJob, FigmaImportStatus
from ..services import figma as figma_service
from ..tenancy import scoped_to
from ..tenant_secrets import get_tenant_secrets

# Mateix volum compartit amb Caddy que la resta de `/uploads`
# (ver routers/home_blocks.py::UPLOADS_DIR) — les imatges importades de
# Figma es serveixen pel mateix camí que qualsevol altra imatge pujada.
UPLOADS_DIR = "/app/uploads"


def _download_and_save_png(url: str) -> str:
    resp = httpx.get(url, timeout=30)
    resp.raise_for_status()
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    filename = f"{uuid.uuid4()}.png"
    with open(os.path.join(UPLOADS_DIR, filename), "wb") as f:
        f.write(resp.content)
    return f"/uploads/{filename}"


def _persist_images_in_tree(node: dict, cache: dict[str, str]) -> None:
    """Substitueix `props.src` (URL temporal de Figma, expira) per una còpia
    pròpia a `/uploads` — recorregut en el mateix arbre ja construït per
    `figma_service.map_node_to_tree`, no es torna a consultar Figma per
    l'estructura, només es baixen els bytes de les imatges trobades.
    `cache` evita baixar dos cops la mateixa imatge si l'arbre la reutilitza."""
    if node.get("type") == "ImageNode":
        src = node.get("props", {}).get("src")
        if src:
            if src not in cache:
                cache[src] = _download_and_save_png(src)
            node["props"]["src"] = cache[src]
    for child in node.get("children") or []:
        _persist_images_in_tree(child, cache)


@celery_app.task(name="figma.import_file")
def import_figma_file(job_id: str, tenant_id: str) -> None:
    db = SessionLocal()
    try:
        with scoped_to(db, uuid.UUID(tenant_id)):
            job = db.get(FigmaImportJob, uuid.UUID(job_id))
            if job is None:
                return
            job.status = FigmaImportStatus.processing
            db.commit()

            try:
                secrets = get_tenant_secrets(uuid.UUID(tenant_id))
                if not secrets.figma_access_token:
                    raise RuntimeError("El tenant no té Figma connectat")
                tree, warnings = figma_service.build_tree_from_frame(
                    secrets.figma_access_token, job.figma_file_key, job.figma_node_id,
                )
                _persist_images_in_tree(tree, {})
                job.result_tree = {"tree": tree, "warnings": warnings}
                job.status = FigmaImportStatus.ready
            except Exception as exc:  # noqa: BLE001 — cualquier fallo se guarda en el job, nunca se pierde silenciosamente
                job.status = FigmaImportStatus.error
                job.error_message = str(exc)
            db.commit()
    finally:
        db.close()
