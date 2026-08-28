"""Cerca i descàrrega de tipografies via Fontsource — mateix patró "API +
caché local" que ja fa servir Discogs (ver services/discogs.py, punt 6 de
CLAUDE.md): l'API pública de Fontsource només es consulta quan l'admin cerca
o tria una tipografia; un cop triada, es descarreguen els fitxers reals i
queden autoallotjats a /uploads — la web pública mai depèn de Fontsource ni
de cap tercer per servir les fonts (evita el problema de RGPD de Google
Fonts: cap petició del visitant surt cap enfora)."""

import os
import time
import uuid

import httpx

FONTSOURCE_API = "https://api.fontsource.org/v1"
FONTSOURCE_CDN = "https://cdn.jsdelivr.net/fontsource"
# Mateix directori pla que favicon/logo/fons de bloc (ver routers/configuracio.py
# i routers/home_blocks.py) — cap subcarpeta, perquè _delete_upload_file ja
# assumeix estructura plana.
UPLOADS_DIR = "/app/uploads"

_cache: dict = {"fonts": None, "fetched_at": 0.0}
_CACHE_TTL_SECONDS = 24 * 3600


async def _all_fonts() -> list[dict]:
    now = time.time()
    if _cache["fonts"] is None or now - _cache["fetched_at"] > _CACHE_TTL_SECONDS:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"{FONTSOURCE_API}/fonts")
            r.raise_for_status()
            _cache["fonts"] = r.json()
            _cache["fetched_at"] = now
    return _cache["fonts"]


async def search_fonts(q: str | None, limit: int = 40) -> list[dict]:
    fonts = await _all_fonts()
    if q and q.strip():
        needle = q.strip().lower()
        fonts = [f for f in fonts if needle in f["family"].lower()]
    fonts = sorted(fonts, key=lambda f: f["family"])[:limit]
    return [
        {"id": f["id"], "family": f["family"], "category": f["category"], "variable": f["variable"]}
        for f in fonts
    ]


async def download_font(font_id: str) -> dict:
    """Descarrega els fitxers reals (pesos 400/700 si existeixen, subset per
    defecte, estil normal) i els desa a /uploads. Retorna
    {family, faces: [{weight, url}]} — prou perquè el crider generi les
    regles @font-face (ver web/app/layout.jsx)."""
    fonts = await _all_fonts()
    font = next((f for f in fonts if f["id"] == font_id), None)
    if font is None:
        raise ValueError(f"Tipografia '{font_id}' no trobada a Fontsource")

    available_weights = font["weights"] or [400]
    weights = [w for w in (400, 700) if w in available_weights] or [available_weights[0]]
    subset = font["defSubset"]

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    faces = []
    async with httpx.AsyncClient(timeout=20) as client:
        for weight in weights:
            # Sense camp "version" a l'API real (l'exemple de la doc no hi
            # coincidia) — "latest" també és vàlid segons la doc del CDN,
            # només amb caché més curta, irrellevant aquí perquè el fitxer
            # es descarrega un cop i queda autoallotjat.
            url = f"{FONTSOURCE_CDN}/fonts/{font_id}@latest/{subset}-{weight}-normal.woff2"
            resp = await client.get(url)
            if resp.status_code != 200:
                continue
            filename = f"{uuid.uuid4()}.woff2"
            with open(os.path.join(UPLOADS_DIR, filename), "wb") as fh:
                fh.write(resp.content)
            faces.append({"weight": weight, "url": f"/uploads/{filename}"})

    if not faces:
        raise ValueError(f"No s'ha pogut descarregar cap pes de '{font['family']}'")

    return {"family": font["family"], "faces": faces}
