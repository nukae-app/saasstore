"""Cliente mínimo de la API REST de Figma — Fase 3 (OAuth + import de tokens
de disseny) i Fase 4 (import estructural: frames -> arbre) de
docs/ARQUITECTURA_DISENY_FIGMA.md.

IMPORTANT (2026-09-28): escrit sense credencials OAuth reals — no s'ha
provat en viu contra l'API de Figma. L'estructura del JSON de `/v1/files/:key`
(mapa `styles` amb metadades + arbre `document` amb `fills`/`style` als nodes
que usen cada estil, `layoutMode` als frames amb auto-layout) és estable des
de fa anys a la documentació pública de Figma, però la primera prova real amb
un fitxer de veritat pot trobar un cas no previst aquí (estils sense cap node
que els faci servir directament, gradients en lloc de color sòlid, variants
de `layoutMode` no contemplades, etc.) — revisar aquest fitxer abans de donar
la Fase 3/4 per tancades de veritat.
"""

import httpx

API_BASE = "https://api.figma.com"


def _client(access_token: str) -> httpx.Client:
    # OAuth2 (Bearer), a diferència del "X-Figma-Token" que usen els personal
    # access tokens — aquí sempre és un token obtingut via el flux OAuth de
    # routers/figma.py, mai un token personal introduït a mà.
    return httpx.Client(base_url=API_BASE, headers={"Authorization": f"Bearer {access_token}"}, timeout=20)


def get_me(access_token: str) -> dict:
    """`GET /v1/me` — per mostrar "Connectat com a..." a l'admin just després
    del callback OAuth (routers/figma.py)."""
    with _client(access_token) as c:
        r = c.get("/v1/me")
        r.raise_for_status()
        return r.json()


def get_file(access_token: str, file_key: str) -> dict:
    """`GET /v1/files/:key` cru — el fitxer sencer (document + styles).
    Usat tant per `get_file_design_styles` (Fase 3) com pel mapeig
    estructural (Fase 4, `build_tree_from_frame`) — es demana un cop per
    crida a cadascuna, no es comparteix una única petició entre totes dues
    (poc trànsit, simplicitat per davant d'optimitzar una crida que Figma ja
    limita per rate limit del costat del tenant, no del nostre)."""
    with _client(access_token) as c:
        r = c.get(f"/v1/files/{file_key}")
        r.raise_for_status()
        return r.json()


def _find_node_with_style(node: dict, style_id: str) -> dict | None:
    """Cerca recursiva del primer node de l'arbre `document` que faci servir
    aquest `style_id` (a `node["styles"]`, p. ex. `{"fill": "1:2"}`) — el mapa
    `styles` d'arrel del fitxer només dona nom/tipus, mai el valor resolt;
    cal trobar un node real que l'apliqui per llegir el color/tipografia."""
    if style_id in (node.get("styles") or {}).values():
        return node
    for child in node.get("children") or []:
        found = _find_node_with_style(child, style_id)
        if found is not None:
            return found
    return None


def _resolve_color(node: dict) -> str | None:
    for fill in node.get("fills") or []:
        if fill.get("type") == "SOLID" and fill.get("visible", True):
            c = fill.get("color") or {}
            r, g, b = round(c.get("r", 0) * 255), round(c.get("g", 0) * 255), round(c.get("b", 0) * 255)
            return f"#{r:02x}{g:02x}{b:02x}"
    return None  # gradient/imatge: no es tradueix a un token de color pla


def _resolve_font_family(node: dict) -> str | None:
    return (node.get("style") or {}).get("fontFamily")


def get_file_design_styles(access_token: str, file_key: str) -> list[dict]:
    """Estils de color i tipografia d'un fitxer Figma, amb el valor ja
    resolt — per mostrar a l'admin (routers/figma.py::list_file_styles) i que
    esculli manualment a quin camp de `ThemeTokens` mapeja cadascun. NUNCA es
    mapeja sol per nom: cap heurística de coincidència de noms aquí a
    propòsit (mateix criteri que Fase 4 amb els frames sense auto-layout —
    ver §6 del document, "no intentar resoldre amb heurístiques fràgils")."""
    data = get_file(access_token, file_key)
    document = data.get("document") or {}
    styles_meta = data.get("styles") or {}
    results = []
    for style_id, meta in styles_meta.items():
        style_type = meta.get("styleType")
        if style_type not in ("FILL", "TEXT"):
            continue
        node = _find_node_with_style(document, style_id)
        if node is None:
            continue
        if style_type == "FILL":
            value = _resolve_color(node)
            kind = "color"
        else:
            value = _resolve_font_family(node)
            kind = "text"
        if value:
            results.append({"figma_style_id": style_id, "name": meta.get("name", ""), "kind": kind, "value": value})
    return results


# --- Fase 4: import estructural (frames -> árbol) ---

_AUTO_LAYOUT_MODES = ("HORIZONTAL", "VERTICAL")
# Tipus de node que SÍ es poden convertir a un `ImageNode` si tenen un fill
# d'imatge — un `TEXT`/`FRAME` amb fill d'imatge és rar però possible, es
# tracta igual que qualsevol altra forma.
_IMAGE_CAPABLE_TYPES = ("RECTANGLE", "ELLIPSE", "VECTOR", "FRAME", "GROUP", "INSTANCE", "COMPONENT", "COMPONENT_SET")


def list_top_level_frames(access_token: str, file_key: str) -> list[dict]:
    """Frames de primer nivell (fills directes d'una `CANVAS`, és a dir d'una
    pàgina del fitxer) que l'admin pot triar per importar — `routers/figma.py
    ::list_frames`. Només es llisten, no es filtra encara per `layoutMode`:
    l'admin ha de poder veure TOTS els frames i que l'error "sense
    auto-layout" surti en importar, no abans (evita un fals "no hi ha res
    per importar" si l'únic frame del fitxer encara no té auto-layout)."""
    data = get_file(access_token, file_key)
    document = data.get("document") or {}
    frames = []
    for canvas in document.get("children") or []:
        if canvas.get("type") != "CANVAS":
            continue
        for node in canvas.get("children") or []:
            if node.get("type") == "FRAME":
                frames.append({
                    "id": node["id"], "name": node.get("name", ""),
                    "page": canvas.get("name", ""),
                    "has_auto_layout": node.get("layoutMode") in _AUTO_LAYOUT_MODES,
                })
    return frames


def _find_node_by_id(node: dict, node_id: str) -> dict | None:
    if node.get("id") == node_id:
        return node
    for child in node.get("children") or []:
        found = _find_node_by_id(child, node_id)
        if found is not None:
            return found
    return None


def _has_image_fill(node: dict) -> bool:
    return any(f.get("type") == "IMAGE" and f.get("visible", True) for f in node.get("fills") or [])


def _collect_image_node_ids(node: dict, out: list[str]) -> None:
    if node.get("type") in _IMAGE_CAPABLE_TYPES and _has_image_fill(node):
        out.append(node["id"])
        return  # no cal baixar més avall d'un node que ja s'exporta sencer com a imatge
    for child in node.get("children") or []:
        _collect_image_node_ids(child, out)


def export_image_urls(access_token: str, file_key: str, node_ids: list[str]) -> dict[str, str]:
    """`GET /v1/images/:key` — sempre PNG, mai SVG: un SVG pot portar
    `<script>`/handlers (superfície XSS real, ver §4 del document) i encara
    no hi ha un sanejador dedicat per a SVG (a diferència de
    `services/sanitize.py::sanitize_custom_css`, pensat per CSS) — exportar
    com a PNG evita aquest forat sencer en comptes d'intentar tancar-lo a
    mitges. Si es vol suport de SVG més endavant, cal un sanejador propi
    abans, no reutilitzar aquest camí tal qual."""
    if not node_ids:
        return {}
    with _client(access_token) as c:
        r = c.get("/v1/images/" + file_key, params={"ids": ",".join(node_ids), "format": "png"})
        r.raise_for_status()
        data = r.json()
    if data.get("err"):
        raise RuntimeError(f"Figma ha tornat un error exportant imatges: {data['err']}")
    return {k: v for k, v in (data.get("images") or {}).items() if v}


def map_node_to_tree(node: dict, image_urls: dict[str, str], warnings: list[str]) -> dict | None:
    """Un node de Figma -> un node del nostre arbre portable
    ({id,type,props,style,children}, ver Page.draft_tree §3), o `None` si no
    es pot mapejar de manera fiable — en aquest cas s'afegeix un avís a
    `warnings` en lloc d'intentar cap heurística (§6: "no s'intenta resoldre
    amb heurístiques fràgils"). L'`id` es deriva de l'id de Figma (mai es
    reutilitza tal qual: porta ':' i Craft.js/React esperen ids sense
    caràcters especials als selectors CSS, ver responsiveStyle.js)."""
    own_id = f"fig{node['id'].replace(':', '_')}"
    node_type = node.get("type")

    if node_type == "TEXT":
        return {
            "id": own_id, "type": "TextNode",
            "props": {"text": {"ca": node.get("characters", "")}},
            "style": {}, "children": [],
        }

    if node_type in _IMAGE_CAPABLE_TYPES and _has_image_fill(node):
        url = image_urls.get(node["id"])
        if not url:
            warnings.append(f"No s'ha pogut exportar la imatge de '{node.get('name', node['id'])}'")
            return None
        return {
            "id": own_id, "type": "ImageNode",
            "props": {"src": url, "alt": {"ca": node.get("name", "")}},
            "style": {}, "children": [],
        }

    if node_type == "FRAME":
        if node.get("layoutMode") not in _AUTO_LAYOUT_MODES:
            warnings.append(f"'{node.get('name', node['id'])}' no té auto-layout — omès (posiciona'l manualment)")
            return None
        children = []
        for child in node.get("children") or []:
            mapped = map_node_to_tree(child, image_urls, warnings)
            if mapped is not None:
                children.append(mapped)
        return {
            "id": own_id, "type": "Stack",
            "props": {
                "direction": {"base": "row" if node["layoutMode"] == "HORIZONTAL" else "column"},
                "gap": {"base": node.get("itemSpacing", 0)},
            },
            "style": {}, "children": children,
        }

    warnings.append(f"'{node.get('name', node['id'])}' ({node_type}) no es pot importar — omès")
    return None


def build_tree_from_frame(access_token: str, file_key: str, node_id: str) -> tuple[dict, list[str]]:
    """Punt d'entrada del import estructural: `node_id` ha de ser un frame de
    primer nivell (ver `list_top_level_frames`) — mai s'importa un fitxer
    sencer d'un cop, sempre un frame concret triat per l'admin."""
    data = get_file(access_token, file_key)
    document = data.get("document") or {}
    frame = _find_node_by_id(document, node_id)
    if frame is None:
        raise ValueError(f"No s'ha trobat el node '{node_id}' al fitxer")
    if frame.get("type") != "FRAME":
        raise ValueError(f"'{frame.get('name', node_id)}' no és un frame")
    if frame.get("layoutMode") not in _AUTO_LAYOUT_MODES:
        raise ValueError(f"'{frame.get('name', node_id)}' no té auto-layout activat — activa'l a Figma i torna-ho a provar")

    image_node_ids: list[str] = []
    _collect_image_node_ids(frame, image_node_ids)
    image_urls = export_image_urls(access_token, file_key, image_node_ids)

    warnings: list[str] = []
    tree = map_node_to_tree(frame, image_urls, warnings)
    # El frame arrel ja s'ha validat abans (auto-layout) — map_node_to_tree
    # no el pot rebutjar, `tree` sempre és un dict aquí.
    tree["id"] = "ROOT"
    return tree, warnings
