"""Tests de la Fase 3 de docs/ARQUITECTURA_DISENY_FIGMA.md (OAuth de Figma +
import de tokens de disseny). Escrit sin credenciales OAuth reales — el
flujo completo `connect` -> Figma -> `callback` no se puede probar aquí (no
hay red ni una cuenta de Figma real); estos tests cubren lo que sí depende
solo de nuestro código: el guard de sesión antes de `connect`, el CRUD de
`FigmaConnection`, y el parseo del JSON de `/v1/files/:key` en
services/figma.py contra un fichero de ejemplo hecho a mano."""

import contextlib
import io
import re

import httpx
from sqlalchemy import select

from app.models import FigmaConnection, Tenant, User
from app.services import figma as figma_service
from app.tenant_secrets import set_tenant_secret


def _login(client, email: str) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _admin_token(client, db) -> str:
    access = _login(client, "admin@example.com")
    user = db.scalar(select(User).where(User.email == "admin@example.com"))
    user.role = "admin"
    db.commit()
    return access


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_figma_status_requereix_admin(client):
    resp = client.get("/admin/figma/status")
    assert resp.status_code in (401, 403)


def test_figma_status_desconnectat_per_defecte(db, client):
    admin = _admin_token(client, db)
    resp = client.get("/admin/figma/status", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json() == {"connected": False, "figma_handle": None, "connected_at": None}


def test_figma_connect_sense_init_403(client):
    resp = client.get("/figma/connect", follow_redirects=False)
    assert resp.status_code == 403


def test_figma_connect_init_despres_connect_redirigeix(db, client):
    """No es pot provar el intercanvi real amb Figma (sense credencials),
    però sí que el guard de sessió (§ mòdul) deixa passar `connect` un cop
    `connect-init` l'ha autoritzat, i que `authorize_redirect` produeix una
    redirecció (302) cap al domini de Figma — sense arribar a fer cap
    petició de xarxa real (`authorize_redirect` només construeix la URL)."""
    admin = _admin_token(client, db)
    init = client.post("/admin/figma/connect-init", headers=_auth(admin))
    assert init.status_code == 204
    resp = client.get("/figma/connect", follow_redirects=False)
    assert resp.status_code == 302
    assert "figma.com" in resp.headers["location"]
    # d'un sol ús: una segona crida sense un nou connect-init torna a fallar
    resp2 = client.get("/figma/connect", follow_redirects=False)
    assert resp2.status_code == 403


def test_figma_disconnect(db, client):
    admin = _admin_token(client, db)
    tenant_id = db.scalar(select(Tenant)).id
    set_tenant_secret(tenant_id, figma_access_token="fake-token", figma_refresh_token="fake-refresh")
    db.add(FigmaConnection(figma_user_id="123", figma_handle="algú"))
    db.commit()

    status = client.get("/admin/figma/status", headers=_auth(admin))
    assert status.json()["connected"] is True

    resp = client.delete("/admin/figma/connection", headers=_auth(admin))
    assert resp.status_code == 204
    assert db.scalar(select(FigmaConnection)) is None

    status2 = client.get("/admin/figma/status", headers=_auth(admin))
    assert status2.json()["connected"] is False


def test_figma_styles_sense_connexio_409(db, client):
    admin = _admin_token(client, db)
    resp = client.post("/admin/figma/styles", json={"file_key": "abc123"}, headers=_auth(admin))
    assert resp.status_code == 409


def test_figma_styles_amb_connexio(db, client, monkeypatch):
    admin = _admin_token(client, db)
    tenant_id = db.scalar(select(Tenant)).id
    set_tenant_secret(tenant_id, figma_access_token="fake-token")

    monkeypatch.setattr(
        figma_service, "get_file_design_styles",
        lambda token, file_key: [{"figma_style_id": "1:2", "name": "Primary", "kind": "color", "value": "#ff0000"}],
    )
    resp = client.post("/admin/figma/styles", json={"file_key": "abc123"}, headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json() == [{"figma_style_id": "1:2", "name": "Primary", "kind": "color", "value": "#ff0000"}]


# --- services/figma.py::get_file_design_styles, contra un fitxer fals ---
# (sense xarxa real — httpx.MockTransport intercepta la petició i torna
# aquest JSON, muntat a mà seguint el format documentat de l'API de Figma;
# és la part que MÉS necessita provar-se perquè és la que no s'ha pogut
# verificar en viu, ver docstring de services/figma.py).

_FAKE_FIGMA_FILE = {
    "document": {
        "id": "0:0",
        "children": [
            {
                "id": "1:1",
                "styles": {"fill": "S:color1"},
                "fills": [{"type": "SOLID", "visible": True, "color": {"r": 1, "g": 0, "b": 0}}],
                "children": [
                    {
                        "id": "1:2",
                        "styles": {"text": "S:text1"},
                        "style": {"fontFamily": "Literata"},
                        "fills": [],
                    },
                ],
            },
        ],
    },
    "styles": {
        "S:color1": {"name": "Primary", "styleType": "FILL"},
        "S:text1": {"name": "Headline", "styleType": "TEXT"},
        "S:orfe": {"name": "Sense node", "styleType": "FILL"},  # cap node el fa servir -> s'omet
        "S:grid1": {"name": "Grid", "styleType": "GRID"},  # tipus no suportat -> s'omet
    },
}


def test_get_file_design_styles(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/files/abc123"
        assert request.headers["authorization"] == "Bearer fake-token"
        return httpx.Response(200, json=_FAKE_FIGMA_FILE)

    real_client = httpx.Client
    monkeypatch.setattr(
        httpx, "Client",
        lambda *a, **kw: real_client(*a, **{**kw, "transport": httpx.MockTransport(handler)}),
    )

    styles = figma_service.get_file_design_styles("fake-token", "abc123")
    assert styles == [
        {"figma_style_id": "S:color1", "name": "Primary", "kind": "color", "value": "#ff0000"},
        {"figma_style_id": "S:text1", "name": "Headline", "kind": "text", "value": "Literata"},
    ]


# --- Fase 4: import estructural (frames -> árbol), services/figma.py ---

_FAKE_FIGMA_FILE_2 = {
    "document": {
        "id": "0:0",
        "children": [
            {
                "id": "10:0",
                "type": "CANVAS",
                "name": "Page 1",
                "children": [
                    {
                        "id": "10:1",
                        "type": "FRAME",
                        "name": "root",
                        "layoutMode": "HORIZONTAL",
                        "itemSpacing": 24,
                        "children": [
                            {"id": "10:2", "type": "TEXT", "name": "Text", "characters": "Hola"},
                            {
                                "id": "10:3",
                                "type": "FRAME",
                                "name": "nested",
                                "layoutMode": "VERTICAL",
                                "itemSpacing": 8,
                                "children": [
                                    {
                                        "id": "10:4",
                                        "type": "RECTANGLE",
                                        "name": "photo",
                                        "fills": [{"type": "IMAGE", "visible": True}],
                                    },
                                ],
                            },
                            {
                                "id": "10:5",
                                "type": "FRAME",
                                "name": "free",
                                "layoutMode": "NONE",
                                "children": [{"id": "10:6", "type": "TEXT", "name": "Perdut", "characters": "Mai s'importa"}],
                            },
                        ],
                    },
                ],
            },
        ],
    },
    "styles": {},
}


def _mock_figma_transport(images_response=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/files/abc123":
            return httpx.Response(200, json=_FAKE_FIGMA_FILE_2)
        if request.url.path == "/v1/images/abc123":
            return httpx.Response(200, json=images_response or {"images": {}})
        raise AssertionError(f"petició inesperada: {request.url}")
    return httpx.MockTransport(handler)


def _patch_httpx_client(monkeypatch, transport):
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda *a, **kw: real_client(*a, **{**kw, "transport": transport}))


def test_list_top_level_frames(monkeypatch):
    _patch_httpx_client(monkeypatch, _mock_figma_transport())
    frames = figma_service.list_top_level_frames("fake-token", "abc123")
    assert frames == [{"id": "10:1", "name": "root", "page": "Page 1", "has_auto_layout": True}]


def test_build_tree_from_frame(monkeypatch):
    _patch_httpx_client(
        monkeypatch,
        _mock_figma_transport({"images": {"10:4": "https://figma-cdn.example/img4.png"}}),
    )
    tree, warnings = figma_service.build_tree_from_frame("fake-token", "abc123", "10:1")

    assert tree["id"] == "ROOT"
    assert tree["type"] == "Stack"
    assert tree["props"]["direction"] == {"base": "row"}
    assert tree["props"]["gap"] == {"base": 24}
    assert len(tree["children"]) == 2  # el "free" (10:5) s'omet sencer

    text_node, nested_stack = tree["children"]
    assert text_node["type"] == "TextNode"
    assert text_node["props"]["text"] == {"ca": "Hola"}

    assert nested_stack["type"] == "Stack"
    assert nested_stack["props"]["direction"] == {"base": "column"}
    assert nested_stack["props"]["gap"] == {"base": 8}
    image_node = nested_stack["children"][0]
    assert image_node["type"] == "ImageNode"
    assert image_node["props"]["src"] == "https://figma-cdn.example/img4.png"

    assert any("free" in w for w in warnings)


def test_build_tree_from_frame_arrel_sense_auto_layout(monkeypatch):
    _patch_httpx_client(monkeypatch, _mock_figma_transport())
    try:
        figma_service.build_tree_from_frame("fake-token", "abc123", "10:5")
        assert False, "havia de fallar"
    except ValueError as exc:
        assert "auto-layout" in str(exc)


# --- Fase 4: endpoints de import-jobs ---

def test_list_frames_sense_connexio_409(db, client):
    admin = _admin_token(client, db)
    resp = client.get("/admin/figma/frames", params={"file_key": "abc123"}, headers=_auth(admin))
    assert resp.status_code == 409


def test_create_import_job(db, client, monkeypatch):
    admin = _admin_token(client, db)
    tenant_id = db.scalar(select(Tenant)).id
    set_tenant_secret(tenant_id, figma_access_token="fake-token")
    monkeypatch.setattr("app.routers.figma.import_figma_file.delay", lambda *a, **k: None)

    resp = client.post(
        "/admin/figma/import-jobs", json={"file_key": "abc123", "node_id": "10:1"}, headers=_auth(admin),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    assert body["tree"] is None


def test_get_import_job_no_trobada(db, client):
    admin = _admin_token(client, db)
    resp = client.get("/admin/figma/import-jobs/00000000-0000-0000-0000-000000000000", headers=_auth(admin))
    assert resp.status_code == 404


def test_apply_import_job_no_llesta_409(db, client, monkeypatch):
    admin = _admin_token(client, db)
    tenant_id = db.scalar(select(Tenant)).id
    set_tenant_secret(tenant_id, figma_access_token="fake-token")
    monkeypatch.setattr("app.routers.figma.import_figma_file.delay", lambda *a, **k: None)
    job = client.post(
        "/admin/figma/import-jobs", json={"file_key": "abc123", "node_id": "10:1"}, headers=_auth(admin),
    ).json()

    resp = client.post(f"/admin/figma/import-jobs/{job['id']}/apply", json={"target_page_id": 1}, headers=_auth(admin))
    assert resp.status_code == 409


# --- Fase 4: la tarea de Celery en sí (llamada directamente, sin .delay) ---

def test_import_figma_file_task(db, client, monkeypatch, tmp_path):
    from app.tasks import figma_import as figma_import_task

    admin = _admin_token(client, db)
    tenant_id = db.scalar(select(Tenant)).id
    set_tenant_secret(tenant_id, figma_access_token="fake-token")
    monkeypatch.setattr("app.routers.figma.import_figma_file.delay", lambda *a, **k: None)
    monkeypatch.setattr(figma_import_task, "UPLOADS_DIR", str(tmp_path))

    job_resp = client.post(
        "/admin/figma/import-jobs", json={"file_key": "abc123", "node_id": "10:1"}, headers=_auth(admin),
    ).json()

    _patch_httpx_client(
        monkeypatch,
        _mock_figma_transport({"images": {"10:4": "https://figma-cdn.example/img4.png"}}),
    )
    monkeypatch.setattr(
        httpx, "get",
        lambda url, timeout=None: httpx.Response(200, content=b"fake-png-bytes", request=httpx.Request("GET", url)),
    )

    figma_import_task.import_figma_file(job_resp["id"], str(tenant_id))

    status_resp = client.get(f"/admin/figma/import-jobs/{job_resp['id']}", headers=_auth(admin))
    body = status_resp.json()
    assert body["status"] == "ready", body.get("error_message")
    image_src = body["tree"]["children"][1]["children"][0]["props"]["src"]
    assert image_src.startswith("/uploads/")
    assert (tmp_path / image_src.removeprefix("/uploads/")).read_bytes() == b"fake-png-bytes"

    page = client.post("/admin/pages", json={"slug": "importada-de-figma"}, headers=_auth(admin)).json()
    apply_resp = client.post(
        f"/admin/figma/import-jobs/{job_resp['id']}/apply",
        json={"target_page_id": page["id"]}, headers=_auth(admin),
    )
    assert apply_resp.status_code == 200
    updated_page = client.get(f"/admin/pages/{page['slug']}", headers=_auth(admin)).json()
    assert updated_page["draft_tree"]["type"] == "Stack"
    assert updated_page["draft_tree"]["children"][0]["props"]["text"] == {"ca": "Hola"}
