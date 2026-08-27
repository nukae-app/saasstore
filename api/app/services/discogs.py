"""Cliente mínimo de la API de Discogs.

Usos: autocompletar metadatos en el alta de discos (admin) y enriquecer
la importación inicial del catálogo. Con token personal, Discogs permite
~60 peticiones/minuto; el cliente espacia las llamadas para respetarlo.
"""

import time

import httpx

BASE = "https://api.discogs.com"
USER_AGENT = "UltraLocalRecords/1.0 +https://ultralocalrecords.example"
_MIN_INTERVAL = 1.1  # segundos entre peticiones (~55/min)
_last_call = 0.0

# Deducció del format canònic (LP/EP/7"/12"/CD/Cassette/Altre, veure
# PesFormat/services/enviament.py) a partir dels tokens que dona Discogs:
# a la cerca vénen tots barrejats ("Vinyl", "LP", "Album"...); a la fitxa
# detallada, separats en `formats[].name` (suport) i `.descriptions` (edició).
# Es prioritza la mida física (7"/12") quan hi ha un marcador d'edició curta
# (Single/Maxi/EP) perquè és el que determina el pes real; un "12", Album"
# normal i corrent es tracta com a LP, no com a single de 12".
_FORMATO_CD = {"CD", "CDR", "CD-R"}
_FORMATO_CASSETTE = {"CASSETTE", "CASS"}
_FORMATO_LP = {"LP", "ALBUM"}
_FORMATO_CURT = {"SINGLE", "MAXI-SINGLE", "MAXI SINGLE", "EP"}

# Els únics valors que pot retornar infer_formato. Útil per detectar releases
# amb `formato` "brut" (text lliure heretat d'abans d'aquest mapeig, p. ex.
# "LP, Album, Ltd") que caldria netejar, a diferència dels que ja tenen un
# dels 7 valors canònics (veure scripts/backfill_formato.py).
FORMATS_CANONICS = {"LP", "EP", '7"', '12"', "CD", "Cassette", "Altre"}


def infer_formato(tokens: list[str]) -> str | None:
    upper = {t.strip().upper() for t in tokens if t}
    if not upper:
        return None
    if upper & _FORMATO_CD:
        return "CD"
    if upper & _FORMATO_CASSETTE:
        return "Cassette"
    es_curt = bool(upper & _FORMATO_CURT)
    if '7"' in upper and es_curt:
        return '7"'
    if ('12"' in upper or '10"' in upper) and es_curt:
        return '12"'
    if upper & _FORMATO_LP:
        return "LP"
    if '7"' in upper:
        return '7"'
    if '12"' in upper or '10"' in upper:
        return '12"'
    if "EP" in upper:
        return "EP"
    if "VINYL" in upper:
        return "LP"
    return "Altre"


def _client(token: str | None) -> httpx.Client:
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Discogs token={token}"
    return httpx.Client(base_url=BASE, headers=headers, timeout=20)


def _throttle() -> None:
    global _last_call
    wait = _MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def search_releases(token: str | None, query: str, per_page: int = 10) -> list[dict]:
    """Búsqueda para el formulario de alta del admin."""
    _throttle()
    with _client(token) as c:
        r = c.get("/database/search", params={"q": query, "type": "release", "per_page": per_page})
        r.raise_for_status()
        results = []
        for hit in r.json().get("results", []):
            title_raw = hit.get("title", "")
            if " - " in title_raw:
                artista, titulo = title_raw.split(" - ", 1)
            else:
                artista, titulo = None, title_raw
            results.append({
                "discogs_release_id": hit.get("id"),
                "artista": artista.strip() if artista else None,
                "titulo": titulo.strip(),
                "anio": hit.get("year"),
                "sello": ", ".join(hit.get("label", [])[:3]) or None,
                "referencia": hit.get("catno"),
                "formato": infer_formato(hit.get("format", [])),
                "genero": ", ".join(hit.get("genre", [])[:3]) or None,
                "imagen_url": hit.get("cover_image"),
            })
        return results


def get_release(token: str | None, release_id: int) -> dict:
    _throttle()
    with _client(token) as c:
        r = c.get(f"/releases/{release_id}")
        r.raise_for_status()
        data = r.json()

        tracklist = [
            {
                "pos": t.get("position", ""),
                "title": t.get("title", ""),
                "duration": t.get("duration", ""),
            }
            for t in data.get("tracklist", [])
            if t.get("type_", "track") == "track" or not t.get("type_")
        ]

        credits = [
            {
                "role": e.get("role", ""),
                "name": e.get("name", ""),
                "tracks": e.get("tracks", ""),
            }
            for e in data.get("extraartists", [])
        ]

        labels = data.get("labels", [])
        sello = ", ".join(f"{lb['name']} – {lb.get('catno', '')}" for lb in labels[:3]) if labels else None

        # La fitxa detallada sí que separa suport ("Vinyl"/"CD"/"Cassette") i
        # edició ("LP"/"Album"/"7"") a `formats[].name`/`.descriptions`, a
        # diferència de la cerca (tot barrejat) — veure infer_formato.
        formato_tokens = []
        for fmt in data.get("formats", []):
            if fmt.get("name"):
                formato_tokens.append(fmt["name"])
            formato_tokens.extend(fmt.get("descriptions", []))

        # El EAN/UPC viene en "identifiers" (no todas las ediciones lo tienen,
        # y algunas tienen varios códigos de barras: nos quedamos con el primero).
        barcodes = [
            i.get("value", "").replace(" ", "").replace("-", "")
            for i in data.get("identifiers", [])
            if i.get("type") == "Barcode" and i.get("value")
        ]

        return {
            "discogs_release_id": data["id"],
            "artista": ", ".join(a["name"] for a in data.get("artists", [])) or None,
            "titulo": data.get("title"),
            "anio": data.get("year"),
            "genero": ", ".join(data.get("genres", [])[:3]) or None,
            "estilos": ", ".join(data.get("styles", [])[:5]) or None,
            "formato": infer_formato(formato_tokens),
            "pais": data.get("country") or None,
            "sello": sello,
            "referencia": labels[0].get("catno") if labels else None,
            "ean": barcodes[0] if barcodes else None,
            "imagen_url": (data.get("images") or [{}])[0].get("uri"),
            "tracklist": tracklist,
            "credits": credits,
        }


def get_release_image(token: str | None, release_id: int) -> str | None:
    """Retorna la URL de la imatge principal d'un release (uri o uri150 com a fallback)."""
    _throttle()
    with _client(token) as c:
        r = c.get(f"/releases/{release_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        images = r.json().get("images", [])
        for img in sorted(images, key=lambda i: i.get("type") != "primary"):
            uri = img.get("uri") or img.get("uri150")
            if uri:
                return uri
    return None


def get_listing(token: str | None, listing_id: int) -> dict | None:
    """Un listing del marketplace (la columna CODI del Excel) -> su release."""
    _throttle()
    with _client(token) as c:
        r = c.get(f"/marketplace/listings/{listing_id}")
        if r.status_code == 404:
            return None  # listing ya borrado en Discogs
        r.raise_for_status()
        data = r.json()
        rel = data.get("release", {})
        return {
            "discogs_release_id": rel.get("id"),
            "imagen_url": rel.get("thumbnail") or None,
            "descripcion_listing": data.get("comments") or None,
        }
