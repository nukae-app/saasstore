"""OAuth de Figma (Fase 3) + import de tokens de disseny (Fase 3) + import
estructural frames->árbol (Fase 4) — docs/ARQUITECTURA_DISENY_FIGMA.md §4.

IMPORTANT (2026-09-28): escrito sin credenciales OAuth reales de Figma
(`FIGMA_CLIENT_ID`/`FIGMA_CLIENT_SECRET` vacíos en `.env` — ver
`config.py`). El flujo espeja el ya existente de Google (`routers/auth.py`)
y nunca se ha probado en vivo — no dar por cerrada la Fase 3 sin esa prueba.

Problema resuelto aquí que Google login no tenía: `require_admin` solo lee
el header `Authorization` (JWT en localStorage, ver `services/security.py`),
pero iniciar el redirect a Figma exige una navegación de página completa,
que nunca lleva ese header. Solución: un POST autenticado normal
(`connect-init`) deja una marca de un solo uso en la sesión de authlib
(la misma `SessionMiddleware` que ya usa Google para `oauth_locale`); la
navegación real a `/figma/connect` solo comprueba esa marca, no el JWT.
"""

import uuid

import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import FigmaConnection, FigmaImportJob, FigmaImportStatus, Page
from ..schemas import (
    FigmaConnectionOut, FigmaFrameOut, FigmaImportApplyIn, FigmaImportJobCreateIn, FigmaImportJobOut,
    FigmaStyleOut, FigmaStylesRequestIn,
)
from ..services import figma as figma_service
from ..services.security import require_admin
from ..tasks.figma_import import import_figma_file
from ..tenancy import tenant_frontend_url
from ..tenant_secrets import get_tenant_secrets, set_tenant_secret

router = APIRouter(prefix="/admin/figma", tags=["figma"])
public_router = APIRouter(prefix="/figma", tags=["figma"])

_settings = get_settings()
oauth = OAuth()
oauth.register(
    name="figma",
    client_id=_settings.figma_client_id,
    client_secret=_settings.figma_client_secret,
    authorize_url="https://www.figma.com/oauth",
    access_token_url="https://www.figma.com/api/oauth/token",
    client_kwargs={"scope": "files:read"},
)

_SESSION_FLAG = "figma_connect_authorized"


@router.get("/status", response_model=FigmaConnectionOut, dependencies=[Depends(require_admin)])
def figma_status(db: Session = Depends(get_db)):
    conn = db.scalar(select(FigmaConnection))
    if conn is None:
        return FigmaConnectionOut(connected=False)
    return FigmaConnectionOut(connected=True, figma_handle=conn.figma_handle, connected_at=conn.connected_at)


@router.post("/connect-init", status_code=204, dependencies=[Depends(require_admin)])
def figma_connect_init(request: Request):
    """Único propósito: dejar la marca de sesión que `public_router` (sin
    `require_admin`, ver docstring del módulo) comprobará en la navegación
    de página completa que viene justo después."""
    request.session[_SESSION_FLAG] = True


@public_router.get("/connect")
async def figma_connect(request: Request):
    if not request.session.pop(_SESSION_FLAG, False):
        raise HTTPException(403, "Cal iniciar la connexió des del panell d'admin")
    redirect_uri = str(request.url_for("figma_callback"))
    return await oauth.figma.authorize_redirect(request, redirect_uri)


@public_router.get("/callback", name="figma_callback")
async def figma_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.figma.authorize_access_token(request)
    access_token = token["access_token"]
    refresh_token = token.get("refresh_token")

    me = figma_service.get_me(access_token)

    set_tenant_secret(request.state.tenant.id, figma_access_token=access_token, figma_refresh_token=refresh_token)

    conn = db.scalar(select(FigmaConnection))
    if conn is None:
        conn = FigmaConnection(figma_user_id=str(me.get("id", "")), figma_handle=me.get("handle"))
        db.add(conn)
    else:
        conn.figma_user_id = str(me.get("id", ""))
        conn.figma_handle = me.get("handle")
    db.commit()

    return RedirectResponse(url=f"{tenant_frontend_url(request.state.tenant)}/admin/figma?connected=1")


@router.delete("/connection", status_code=204, dependencies=[Depends(require_admin)])
def figma_disconnect(request: Request, db: Session = Depends(get_db)):
    conn = db.scalar(select(FigmaConnection))
    if conn is not None:
        db.delete(conn)
        db.commit()
    set_tenant_secret(request.state.tenant.id, figma_access_token=None, figma_refresh_token=None)


@router.post("/styles", response_model=list[FigmaStyleOut], dependencies=[Depends(require_admin)])
def list_file_styles(payload: FigmaStylesRequestIn, request: Request):
    secrets_ = get_tenant_secrets(request.state.tenant.id)
    if not secrets_.figma_access_token:
        raise HTTPException(409, "El tenant no té Figma connectat")
    try:
        return figma_service.get_file_design_styles(secrets_.figma_access_token, payload.file_key)
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Error consultant Figma: {exc}") from exc


# --- Fase 4: import estructural (frames -> árbol) ---

def _job_out(job: FigmaImportJob) -> FigmaImportJobOut:
    result = job.result_tree or {}
    return FigmaImportJobOut(
        id=job.id, status=job.status.value, error_message=job.error_message,
        tree=result.get("tree"), warnings=result.get("warnings", []), target_page_id=job.target_page_id,
    )


@router.get("/frames", response_model=list[FigmaFrameOut], dependencies=[Depends(require_admin)])
def list_frames(file_key: str, request: Request):
    secrets_ = get_tenant_secrets(request.state.tenant.id)
    if not secrets_.figma_access_token:
        raise HTTPException(409, "El tenant no té Figma connectat")
    try:
        return figma_service.list_top_level_frames(secrets_.figma_access_token, file_key)
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Error consultant Figma: {exc}") from exc


@router.post("/import-jobs", response_model=FigmaImportJobOut, status_code=201, dependencies=[Depends(require_admin)])
def create_import_job(payload: FigmaImportJobCreateIn, request: Request, db: Session = Depends(get_db)):
    secrets_ = get_tenant_secrets(request.state.tenant.id)
    if not secrets_.figma_access_token:
        raise HTTPException(409, "El tenant no té Figma connectat")
    job = FigmaImportJob(figma_file_key=payload.file_key, figma_node_id=payload.node_id)
    db.add(job)
    db.commit()
    db.refresh(job)
    import_figma_file.delay(str(job.id), str(request.state.tenant.id))
    return _job_out(job)


def _get_job_or_404(job_id: str, db: Session) -> FigmaImportJob:
    try:
        job = db.get(FigmaImportJob, uuid.UUID(job_id))
    except ValueError:
        raise HTTPException(404, "Importació no trobada") from None
    if job is None:
        raise HTTPException(404, "Importació no trobada")
    return job


@router.get("/import-jobs/{job_id}", response_model=FigmaImportJobOut, dependencies=[Depends(require_admin)])
def get_import_job(job_id: str, db: Session = Depends(get_db)):
    return _job_out(_get_job_or_404(job_id, db))


@router.post("/import-jobs/{job_id}/apply", response_model=FigmaImportJobOut, dependencies=[Depends(require_admin)])
def apply_import_job(job_id: str, payload: FigmaImportApplyIn, db: Session = Depends(get_db)):
    """Copia `job.result_tree.tree` a `Page.draft_tree` de la página elegida
    — mai a `published_tree` directament (mateix criteri que qualsevol altra
    edició de `draft_tree`, ver routers/pages.py): el tenant revisa a
    l'editor i publica quan vulgui, no abans."""
    job = _get_job_or_404(job_id, db)
    if job.status != FigmaImportStatus.ready:
        raise HTTPException(409, f"La importació encara no està llesta (status: {job.status.value})")
    page = db.get(Page, payload.target_page_id)
    if page is None:
        raise HTTPException(404, "Pàgina de destí no trobada")
    page.draft_tree = job.result_tree["tree"]
    job.target_page_id = payload.target_page_id
    db.commit()
    db.refresh(job)
    return _job_out(job)
