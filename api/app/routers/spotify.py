"""OAuth de Spotify + recomanacions de catàleg."""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import SpotifyConnection, Tenant, User
from ..services import spotify as svc
from ..services.security import get_current_user
from ..tenancy import tenant_frontend_url
from ..tenant_secrets import get_tenant_secrets

log = logging.getLogger(__name__)

def require_spotify_enabled() -> None:
    """Kill switch global: amb spotify_enabled=False totes les rutes del
    router protegit responen 404, com si el mòdul no existís."""
    if not get_settings().spotify_enabled:
        raise HTTPException(404)


router = APIRouter(
    prefix="/auth/spotify", tags=["spotify"], dependencies=[Depends(require_spotify_enabled)]
)
# Sense la dependència anterior: el frontend l'ha de poder consultar encara
# que el mòdul estigui desactivat, per decidir si mostra la secció Spotify.
public_router = APIRouter(prefix="/auth/spotify", tags=["spotify"])

_SESSION_KEY = "spotify_link"


@public_router.get("/enabled")
def spotify_enabled():
    return {"enabled": get_settings().spotify_enabled}


def _redirect_uri(tenant: Tenant) -> str:
    # No fem servir request.url_for: uvicorn no coneix l'esquema public (https)
    # perquè Caddy hi parla per HTTP intern, i generaria una redirect_uri http://
    # que no fa match amb la registrada al dashboard de Spotify.
    return f"{tenant_frontend_url(tenant)}/api/auth/spotify/callback"


@router.post("/init")
async def spotify_init(request: Request, user: User = Depends(get_current_user)):
    """Inicia el flux OAuth. Desa user_id a la sessió i retorna la URL de Spotify."""
    tenant = request.state.tenant
    secrets_ = get_tenant_secrets(tenant.id)
    if not secrets_.spotify_client_id:
        raise HTTPException(503, "Spotify no configurat per a aquesta botiga")
    state = secrets.token_urlsafe(16)
    request.session[_SESSION_KEY] = {"uid": str(user.id), "state": state}
    url = svc.build_authorize_url(secrets_.spotify_client_id, _redirect_uri(tenant), state)
    return {"url": url}


@router.get("/callback", name="spotify_callback")
async def spotify_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    tenant = request.state.tenant
    secrets_ = get_tenant_secrets(tenant.id)
    frontend = tenant_frontend_url(tenant)

    if error or not code:
        return RedirectResponse(f"{frontend}/compte?spotify=error")

    session_data = request.session.pop(_SESSION_KEY, None)
    if not session_data or session_data.get("state") != state:
        return RedirectResponse(f"{frontend}/compte?spotify=error")

    try:
        token_data = await svc.exchange_code(
            code, _redirect_uri(tenant), secrets_.spotify_client_id, secrets_.spotify_client_secret
        )
    except Exception:
        return RedirectResponse(f"{frontend}/compte?spotify=error")

    try:
        profile = await svc.get_profile(token_data["access_token"])
        spotify_user_id = profile["id"]
        display_name = profile.get("display_name") or profile.get("id")
    except Exception:
        return RedirectResponse(f"{frontend}/compte?spotify=error")

    user_id = session_data["uid"]
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=token_data.get("expires_in", 3600))

    conn = db.scalar(select(SpotifyConnection).where(SpotifyConnection.user_id == user_id))
    if conn:
        conn.spotify_user_id = spotify_user_id
        conn.display_name = display_name
        conn.access_token = token_data["access_token"]
        conn.refresh_token = token_data.get("refresh_token", conn.refresh_token)
        conn.token_expires_at = expires
    else:
        db.add(SpotifyConnection(
            user_id=user_id,
            spotify_user_id=spotify_user_id,
            display_name=display_name,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", ""),
            token_expires_at=expires,
        ))
    db.commit()

    return RedirectResponse(f"{frontend}/compte?spotify=ok")


@router.get("/status")
def spotify_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    conn = db.scalar(select(SpotifyConnection).where(SpotifyConnection.user_id == user.id))
    if not conn:
        return {"connected": False}
    return {"connected": True, "display_name": conn.display_name}


@router.delete("/disconnect", status_code=204)
def spotify_disconnect(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    conn = db.scalar(select(SpotifyConnection).where(SpotifyConnection.user_id == user.id))
    if conn:
        db.delete(conn)
        db.commit()


@router.get("/library")
async def spotify_library(
    request: Request,
    time_range: Literal["short_term", "medium_term", "long_term"] = "medium_term",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Artistes i discos escoltats a Spotify, agrupats i comparats
    directament (sense IA) amb el catàleg en 3 nivells: disc exacte, només
    l'artista, o cap dels dos."""
    secrets_ = get_tenant_secrets(request.state.tenant.id)
    conn = db.scalar(select(SpotifyConnection).where(SpotifyConnection.user_id == user.id))
    if not conn:
        raise HTTPException(404, "Spotify no connectat")

    try:
        access_token = await svc.ensure_fresh_token(
            conn, secrets_.spotify_client_id, secrets_.spotify_client_secret, db
        )
        artists_meta = await svc.get_top_artists(access_token, limit=50, time_range=time_range)
        tracks = await svc.get_top_tracks(access_token, limit=50, time_range=time_range)
    except Exception:
        log.exception("Error carregant /auth/spotify/library (time_range=%s)", time_range)
        raise HTTPException(502, "Error llegint dades de Spotify")

    if artists_meta is None or tracks is None:
        raise HTTPException(502, "Token de Spotify caducat, torna a connectar")

    return svc.build_listening_library(db, artists_meta, tracks)


@router.get("/artists/{spotify_id}/albums")
async def spotify_artist_albums(
    request: Request,
    spotify_id: str,
    artist_name: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Discografia completa d'un artista a Spotify (no només el que l'usuari
    ha escoltat), comparada amb el catàleg disc a disc, sense IA."""
    secrets_ = get_tenant_secrets(request.state.tenant.id)
    conn = db.scalar(select(SpotifyConnection).where(SpotifyConnection.user_id == user.id))
    if not conn:
        raise HTTPException(404, "Spotify no connectat")

    try:
        access_token = await svc.ensure_fresh_token(
            conn, secrets_.spotify_client_id, secrets_.spotify_client_secret, db
        )
        albums = await svc.get_artist_albums(access_token, spotify_id)
    except Exception:
        log.exception("Error carregant discografia de l'artista %s (%s)", artist_name, spotify_id)
        raise HTTPException(502, "Error llegint dades de Spotify")

    if albums is None:
        raise HTTPException(502, "Token de Spotify caducat, torna a connectar")

    return svc.match_albums_direct(db, artist_name, albums)


@router.get("/recommendations")
async def spotify_recommendations(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    secrets_ = get_tenant_secrets(request.state.tenant.id)
    conn = db.scalar(select(SpotifyConnection).where(SpotifyConnection.user_id == user.id))
    if not conn:
        raise HTTPException(404, "Spotify no connectat")

    try:
        access_token = await svc.ensure_fresh_token(
            conn, secrets_.spotify_client_id, secrets_.spotify_client_secret, db
        )
        artists = await svc.get_top_artists(access_token)
    except Exception:
        raise HTTPException(502, "Error llegint dades de Spotify")

    if artists is None:
        raise HTTPException(502, "Token de Spotify caducat, torna a connectar")

    spotify_artist_names = [a["name"] for a in artists]

    # Expandeix el perfil de gust via Claude — si falla, continua amb els artistes originals
    expanded = await svc.expand_taste_with_ai(spotify_artist_names)
    if expanded:
        search_names = list(dict.fromkeys(spotify_artist_names + expanded.get("artists", [])))
        ai_expanded = True
    else:
        search_names = spotify_artist_names
        ai_expanded = False

    releases = svc.get_catalog_matches(db, search_names)

    return {
        "top_artists": spotify_artist_names[:5],
        "ai_expanded": ai_expanded,
        "releases": [
            {
                "id": str(r.id),
                "artista": r.artista,
                "titulo": r.title,
                "anio": r.anio,
                "formato": r.formato,
                "genero": r.genero,
                "imagen_url": r.image_url,
                "etiquetes": [],
                "items": [
                    {
                        "id": str(i.id),
                        "precio": float(i.price),
                        "condicion": i.condition.value,
                        "estado_disco": i.estado_disco,
                        "estado_funda": i.estado_funda,
                        "status": i.status.value,
                        "cantidad": i.quantity,
                        "cantidad_reservada": i.reserved_quantity,
                    }
                    for i in r.items
                ],
            }
            for r in releases
        ],
    }
