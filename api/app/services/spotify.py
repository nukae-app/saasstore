"""Integració amb l'API de Spotify per a recomanacions de catàleg."""

import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import anthropic
import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import Item, ItemStatus, Release, SpotifyConnection

log = logging.getLogger(__name__)

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_URL = "https://api.spotify.com/v1"
SCOPE = "user-top-read"
SIMILARITY_THRESHOLD = 0.3


async def get_app_access_token(client_id: str, client_secret: str) -> str:
    """Token d'aplicació (client credentials, sense usuari) per a cerques al
    catàleg públic de Spotify — no depèn que cap client tingui Spotify
    connectat."""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
        )
        r.raise_for_status()
        return r.json()["access_token"]


async def search_album(access_token: str, artist: str, title: str) -> str | None:
    """Cerca l'àlbum al catàleg de Spotify per artista+títol; retorna l'id
    del primer resultat o None si no en troba cap."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{API_URL}/search",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"q": f"artist:{artist} album:{title}", "type": "album", "limit": 1},
        )
        r.raise_for_status()
        items = r.json().get("albums", {}).get("items", [])
        return items[0]["id"] if items else None


def build_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": SCOPE,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(code: str, redirect_uri: str, client_id: str, client_secret: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            TOKEN_URL,
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
            auth=(client_id, client_secret),
        )
        r.raise_for_status()
        return r.json()


async def do_refresh(refresh_tok: str, client_id: str, client_secret: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": refresh_tok},
            auth=(client_id, client_secret),
        )
        r.raise_for_status()
        return r.json()


async def get_profile(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/me", headers={"Authorization": f"Bearer {access_token}"})
        r.raise_for_status()
        return r.json()


async def get_top_artists(access_token: str, limit: int = 20, time_range: str = "medium_term") -> list[dict] | None:
    """Retorna els top artistes o None si el token ha caducat."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{API_URL}/me/top/artists",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"limit": limit, "time_range": time_range},
        )
        if r.status_code == 401:
            return None
        r.raise_for_status()
        return r.json().get("items", [])


async def get_artist_albums(access_token: str, artist_id: str, market: str = "ES") -> list[dict] | None:
    """Discografia completa d'un artista (àlbums + compilacions), independent
    del que l'usuari hagi escoltat. Deduplica per nom (Spotify sol repetir el
    mateix disc per a diferents mercats/edicions), quedant-se la primera
    aparició (Spotify les retorna per data de llançament descendent)."""
    albums: list[dict] = []
    seen_names: set[str] = set()
    url = f"{API_URL}/artists/{artist_id}/albums"
    # Nota: tot i que la doc de Spotify parla de limit fins a 50, aquest
    # endpoint en concret respon 400 "Invalid limit" per a qualsevol valor
    # per sobre de 10 (comprovat manualment); per això es queda curt i es
    # compensa paginant més cops.
    params = {"include_groups": "album,compilation", "market": market, "limit": 10}
    async with httpx.AsyncClient() as client:
        for _ in range(20):  # com a molt ~200 àlbums, de sobres per a un artista de botiga
            r = await client.get(url, headers={"Authorization": f"Bearer {access_token}"}, params=params)
            if r.status_code == 401:
                return None
            if r.status_code >= 400:
                log.error("Spotify GET %s -> %s: %s", r.request.url, r.status_code, r.text)
            r.raise_for_status()
            data = r.json()
            for album in data.get("items", []):
                key = album["name"].strip().lower()
                if key in seen_names:
                    continue
                seen_names.add(key)
                albums.append(album)
            next_url = data.get("next")
            if not next_url:
                break
            url, params = next_url, None
    return albums


async def get_top_tracks(access_token: str, limit: int = 50, time_range: str = "medium_term") -> list[dict] | None:
    """Retorna les top cançons (amb el seu àlbum) o None si el token ha caducat."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{API_URL}/me/top/tracks",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"limit": limit, "time_range": time_range},
        )
        if r.status_code == 401:
            return None
        r.raise_for_status()
        return r.json().get("items", [])


async def ensure_fresh_token(conn: SpotifyConnection, client_id: str, client_secret: str, db: Session) -> str:
    now = datetime.now(timezone.utc)
    expires = conn.token_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires > now + timedelta(minutes=2):
        return conn.access_token
    data = await do_refresh(conn.refresh_token, client_id, client_secret)
    conn.access_token = data["access_token"]
    conn.token_expires_at = now + timedelta(seconds=data["expires_in"])
    if "refresh_token" in data:
        conn.refresh_token = data["refresh_token"]
    db.commit()
    return conn.access_token


async def expand_taste_with_ai(artist_names: list[str]) -> dict:
    """
    Usa Claude Haiku per expandir els artistes favorits en termes de cerca
    més amplis: artistes relacionats, gèneres, estils i segells rellevants.
    Retorna {'artists': [...], 'genres': [...]} o None si falla.
    """
    if not artist_names:
        return None
    try:
        client = anthropic.AsyncAnthropic()
        artists_str = ", ".join(artist_names[:10])
        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    f"A vinyl record store customer likes these artists: {artists_str}.\n"
                    "List related artists and genres they'd likely enjoy in our catalog. "
                    "Focus on artists realistically found in a small indie record shop (no obscure micro-artists). "
                    "Return ONLY valid JSON, no explanation:\n"
                    '{"artists": ["name1", "name2", ...], "genres": ["genre1", "genre2", ...]}\n'
                    "Up to 15 artists and 8 genres."
                ),
            }],
        )
        return json.loads(message.content[0].text)
    except Exception as e:
        log.warning("Claude expansion failed: %s", e)
        return None


def get_catalog_matches(db: Session, artist_names: list[str], limit: int = 12) -> list[Release]:
    """Cerca releases en stock que coincideixin amb els artistes via pg_trgm."""
    if not artist_names:
        return []

    names_lower = [n.lower() for n in artist_names[:30]]

    sim_conditions = [
        func.similarity(func.lower(Release.artista), name) > SIMILARITY_THRESHOLD
        for name in names_lower
    ]
    sim_exprs = [func.similarity(func.lower(Release.artista), name) for name in names_lower]
    score_expr = func.greatest(*sim_exprs) if len(sim_exprs) > 1 else sim_exprs[0]

    stmt = (
        select(Release, score_expr.label("score"))
        .join(Item, (Item.release_id == Release.id) & (Item.status == ItemStatus.disponible))
        .where(or_(*sim_conditions))
        .group_by(Release.id)
        .order_by(score_expr.desc())
        .limit(limit)
    )

    return [row.Release for row in db.execute(stmt).all()]


ARTIST_MATCH_THRESHOLD = 0.45
TITLE_MATCH_THRESHOLD = 0.35


def _find_exact_release(db: Session, artist: str, title: str) -> Release | None:
    """Un disc concret: artista I títol similars, amb estoc disponible."""
    artist_sim = func.similarity(func.lower(Release.artista), artist.lower())
    title_sim = func.similarity(func.lower(Release.titulo), title.lower())
    stmt = (
        select(Release)
        .join(Item, (Item.release_id == Release.id) & (Item.status == ItemStatus.disponible))
        .where(artist_sim > ARTIST_MATCH_THRESHOLD, title_sim > TITLE_MATCH_THRESHOLD)
        .group_by(Release.id)
        .order_by((artist_sim + title_sim).desc())
        .limit(1)
    )
    return db.scalar(stmt)


def _artist_in_catalog(db: Session, artist: str) -> bool:
    """L'artista té algun disc amb estoc disponible, sigui quin sigui."""
    artist_sim = func.similarity(func.lower(Release.artista), artist.lower())
    stmt = (
        select(Release.id)
        .join(Item, (Item.release_id == Release.id) & (Item.status == ItemStatus.disponible))
        .where(artist_sim > ARTIST_MATCH_THRESHOLD)
        .limit(1)
    )
    return db.scalar(stmt) is not None


def _match_album(db: Session, artist_name: str, artist_in_catalog: bool, titulo: str) -> tuple[str, Release | None]:
    release = _find_exact_release(db, artist_name, titulo)
    if release:
        return "exacte", release
    return ("artista" if artist_in_catalog else "cap"), None


def _release_dict(release: Release | None) -> dict | None:
    if not release:
        return None
    return {
        "id": str(release.id),
        "artista": release.artista,
        "titulo": release.titulo,
        "imagen_url": release.imagen_url,
        "anio": release.anio,
        "formato": release.formato,
    }


def match_albums_direct(db: Session, artist_name: str, albums: list[dict]) -> list[dict]:
    """Compara la discografia completa d'un artista (de get_artist_albums,
    independent del que l'usuari hagi escoltat) amb el catàleg, disc a disc
    i sense pas per IA."""
    artist_in_catalog = _artist_in_catalog(db, artist_name)
    result = []
    for album in albums:
        images = album.get("images") or []
        titulo = album["name"]
        estat, release = _match_album(db, artist_name, artist_in_catalog, titulo)
        result.append({
            "spotify_album_id": album["id"],
            "titulo": titulo,
            "imagen_url": images[0]["url"] if images else None,
            "any": (album.get("release_date") or "")[:4] or None,
            "tipus": album.get("album_type"),
            "estat": estat,
            "release": _release_dict(release),
        })
    return result


def build_listening_library(db: Session, artists_meta: list[dict], tracks: list[dict]) -> list[dict]:
    """Agrupa les top cançons de Spotify per artista i, dins de cada artista,
    pels seus àlbums (deduplicant per id d'àlbum), i compara cada disc amb el
    catàleg en 3 nivells — sense pas per IA, a diferència de get_catalog_matches:
    'exacte' (aquest disc concret), 'artista' (el tenim, però un altre disc
    seu) o 'cap'. artists_meta ve de get_top_artists (per la imatge i gèneres
    de l'artista); tracks ve de get_top_tracks (per als àlbums)."""
    meta_by_name = {a["name"].lower(): a for a in artists_meta}

    artists_order: list[str] = []
    by_artist: dict[str, dict] = {}

    # Sembra amb els top artistes (fins a 50): garanteix que sempre en surten
    # tants com Spotify en retorni, encara que no tinguem cap àlbum seu entre
    # les top cançons (que és una mostra molt més petita, 50 cançons en total
    # repartides entre tots els artistes).
    for a in artists_meta:
        if a["name"] not in by_artist:
            by_artist[a["name"]] = {"spotify_id": a["id"], "albums": {}}
            artists_order.append(a["name"])

    for track in tracks:
        track_artists = track.get("artists") or []
        album = track.get("album")
        if not track_artists or not album:
            continue
        artist_name = track_artists[0]["name"]
        if artist_name not in by_artist:
            by_artist[artist_name] = {"spotify_id": track_artists[0]["id"], "albums": {}}
            artists_order.append(artist_name)

        albums = by_artist[artist_name]["albums"]
        if album["id"] not in albums:
            images = album.get("images") or []
            albums[album["id"]] = {
                "spotify_album_id": album["id"],
                "titulo": album["name"],
                "imagen_url": images[0]["url"] if images else None,
                "any": (album.get("release_date") or "")[:4] or None,
                "tipus": album.get("album_type"),
            }

    result = []
    for artist_name in artists_order:
        data = by_artist[artist_name]
        artist_in_catalog = _artist_in_catalog(db, artist_name)

        albums_out = []
        any_exacte = False
        for album in data["albums"].values():
            estat, release = _match_album(db, artist_name, artist_in_catalog, album["titulo"])
            if estat == "exacte":
                any_exacte = True
            albums_out.append({**album, "estat": estat, "release": _release_dict(release)})

        meta = meta_by_name.get(artist_name.lower())
        meta_images = (meta.get("images") if meta else None) or []
        result.append({
            "spotify_id": data["spotify_id"],
            "name": artist_name,
            "image_url": meta_images[0]["url"] if meta_images else (albums_out[0]["imagen_url"] if albums_out else None),
            "genres": meta.get("genres", []) if meta else [],
            "estat": "exacte" if any_exacte else ("artista" if artist_in_catalog else "cap"),
            "albums": albums_out,
        })

    return result
