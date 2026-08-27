"""Tests de la Fase 4 del roadmap de superadmin (ver plan
/Users/paumartinez/.claude/plans/rustling-foraging-wind.md): el endpoint
`ask` que consulta Caddy antes de pedir un certificado TLS on-demand para
un dominio de tenant. Sin este filtro, cualquier hostname que resolviera a
este servidor podría disparar peticiones de certificado a Let's Encrypt."""

from app.models import Tenant


def test_dominio_de_tenant_activo_devuelve_200(db, client):
    db.add(Tenant(slug="florqa", domain="florqa.example.com", nombre="Florqa", vertical_id="records"))
    db.commit()
    resp = client.get("/internal/caddy/ask-domain", params={"domain": "florqa.example.com"})
    assert resp.status_code == 200


def test_dominio_desconocido_devuelve_404(client):
    resp = client.get("/internal/caddy/ask-domain", params={"domain": "no-existe.example.com"})
    assert resp.status_code == 404


def test_dominio_de_tenant_suspendido_devuelve_404(db, client):
    """Confirma el enganche con la Fase 2: un tenant con `activo=False` no
    debe poder conseguir un certificado TLS nuevo."""
    db.add(Tenant(
        slug="suspendida", domain="suspendida.example.com", nombre="Suspendida",
        vertical_id="records", activo=False,
    ))
    db.commit()
    resp = client.get("/internal/caddy/ask-domain", params={"domain": "suspendida.example.com"})
    assert resp.status_code == 404


def test_falta_el_parametro_domain(client):
    resp = client.get("/internal/caddy/ask-domain")
    assert resp.status_code == 422
