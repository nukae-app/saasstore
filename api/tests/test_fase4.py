"""Tests de la Fase 4 (ver plan /Users/paumartinez/.claude/plans/swift-gathering-bengio.md):
aislamiento por tenant de las tablas de ERP/contabilidad/club que nunca lo
tuvieron, el arreglo de ConfiguracioSubscripcio (deja de ser una fila fija
id=1), el cierre de los huecos de discogs_habilitat, y el round-trip de los
campos de la extensión de floristeria en Release."""

import contextlib
import io
import re
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    CategoriaDespesa, Compra, ConfiguracioBotiga, ConfiguracioSubscripcio, Despesa, Proveedor,
    Release, Tenant, TipoCompra, User,
)
from app.routers.admin_subscripcions import _get_or_create_config
from app.services.discogs_sync import get_discogs_token_if_enabled
from app.tenancy import scoped_to


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


def _seed_second_tenant(db, slug="tenant-b-fase4", domain="b-fase4.testserver", vertical_id="records") -> Tenant:
    tenant = Tenant(slug=slug, domain=domain, nombre="Tenant B", vertical_id=vertical_id)
    db.add(tenant)
    db.commit()
    return tenant


# ---------------------------------------------------------------------------
# A: aislamiento de ERP/contabilidad/club
# ---------------------------------------------------------------------------

def test_compra_de_un_tenant_no_es_visible_en_otro(db):
    tenant_a_id = db.info["tenant_id"]
    tenant_b = _seed_second_tenant(db)

    compra_a = Compra(type=TipoCompra.particular, individual_name="Fulano", date=datetime.now(timezone.utc))
    db.add(compra_a)
    db.commit()

    db.info["tenant_id"] = tenant_b.id
    assert db.scalars(select(Compra)).all() == []

    db.info["tenant_id"] = tenant_a_id
    assert db.scalar(select(Compra)).id == compra_a.id


def test_despesa_de_un_tenant_no_es_visible_en_otro(db):
    tenant_a_id = db.info["tenant_id"]
    tenant_b = _seed_second_tenant(db)

    despesa_a = Despesa(
        invoice_date=date.today(), supplier_name="Llum SA",
        category=CategoriaDespesa.subministraments, concept="Factura llum", taxable_base=Decimal("100.00"),
        vat_pct=Decimal("21.00"), vat_amount=Decimal("21.00"), total=Decimal("121.00"),
    )
    db.add(despesa_a)
    db.commit()

    db.info["tenant_id"] = tenant_b.id
    assert db.scalars(select(Despesa)).all() == []

    db.info["tenant_id"] = tenant_a_id
    assert db.scalar(select(Despesa)).id == despesa_a.id


def test_proveedor_de_un_tenant_no_es_visible_en_otro(db):
    """Bug real de aislamiento (no solo `Base` -> `TenantScoped`, ya
    detectado antes de este plan): `Proveedor` estaba detrás del mismo
    router admin que tablas correctamente aisladas, sin tenant_id propio."""
    tenant_a_id = db.info["tenant_id"]
    tenant_b = _seed_second_tenant(db)

    proveedor_a = Proveedor(name="Distribuidora X")
    db.add(proveedor_a)
    db.commit()

    db.info["tenant_id"] = tenant_b.id
    assert db.scalars(select(Proveedor)).all() == []

    db.info["tenant_id"] = tenant_a_id
    assert db.scalar(select(Proveedor)).id == proveedor_a.id


# ---------------------------------------------------------------------------
# A.1: ConfiguracioSubscripcio deja de ser una fila fija id=1
# ---------------------------------------------------------------------------

def test_configuracio_subscripcio_es_propia_de_cada_tenant(db):
    """Antes de este arreglo, `_get_or_create_config` hacía `db.get(..., 1)`
    — con tenant_id como clave natural, el segundo tenant chocaría con la
    fila id=1 del primero (o, peor, la vería como si fuera suya)."""
    tenant_a_id = db.info["tenant_id"]
    tenant_b = _seed_second_tenant(db)

    config_a = _get_or_create_config(db)
    config_a.preu_per_disc = Decimal("30.00")
    db.commit()

    with scoped_to(db, tenant_b.id):
        config_b = _get_or_create_config(db)
        assert config_b.id != config_a.id
        assert config_b.preu_per_disc == 0  # valor por defecto, no el de tenant A

    db.info["tenant_id"] = tenant_a_id
    db.refresh(config_a)
    assert config_a.preu_per_disc == Decimal("30.00")


# ---------------------------------------------------------------------------
# D: huecos de discogs_habilitat
# ---------------------------------------------------------------------------

def test_get_discogs_token_if_enabled_respeta_el_interruptor(db, monkeypatch):
    tenant_id = db.info["tenant_id"]
    config = db.scalar(select(ConfiguracioBotiga))
    assert config.discogs_habilitat is True  # fixture de conftest.py

    monkeypatch.setattr(
        "app.services.discogs_sync.get_tenant_secrets",
        lambda tid: type("S", (), {"discogs_token": "fake-token-todavia-presente"})(),
    )
    assert get_discogs_token_if_enabled(db, tenant_id) == "fake-token-todavia-presente"

    config.discogs_habilitat = False
    db.commit()
    assert get_discogs_token_if_enabled(db, tenant_id) is None, (
        "un token presente en secretos no debe usarse si discogs_habilitat está en False"
    )


def test_resolver_csv_comanda_404_si_discogs_desactivado(db, client):
    admin = _admin_token(client, db)
    config = db.scalar(select(ConfiguracioBotiga))
    config.discogs_habilitat = False
    db.commit()

    resp = client.post(
        "/admin/comandas/resolver-csv",
        files={"file": ("comanda.csv", b"discogs_release_id,cantidad,precio_unitario_estimado\n1,1,10\n", "text/csv")},
        headers=_auth(admin),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# C: extensión de floristeria (round-trip vía los endpoints existentes)
# ---------------------------------------------------------------------------

def test_release_floristeria_round_trip(db, client):
    # El aislamiento server-side por vertical (ver
    # docs/ARQUITECTURA_CORE_VERTICAL.md §11, Fase 3) solo aplica la
    # extensión floristeria si el tenant es del vertical floristry — el
    # tenant de pruebas por defecto es records, así que hay que conmutarlo
    # para este test.
    tenant = db.get(Tenant, db.info["tenant_id"])
    tenant.vertical_id = "floristry"
    db.commit()

    admin = _admin_token(client, db)

    resp = client.post(
        "/admin/releases",
        json={
            "artista": "Floristeria Test", "title": "Ram de roses", "ean": "1234567890123",
            "color": "vermell", "tipus_flor": "rosa", "durabilitat_dies": 7,
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    release_id = resp.json()["id"]

    listado = client.get("/admin/releases", headers=_auth(admin)).json()
    creado = next(r for r in listado["releases"] if r["id"] == release_id)
    assert creado["color"] == "vermell"
    assert creado["tipus_flor"] == "rosa"
    assert creado["durabilitat_dies"] == 7

    # Actualizar los campos de floristeria vía PUT (no solo POST) — es donde
    # el `setattr` a ciegas original habría fallado en silencio.
    resp = client.put(
        f"/admin/releases/{release_id}",
        json={"artista": "Floristeria Test", "title": "Ram de roses", "color": "blanc"},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    listado = client.get("/admin/releases", headers=_auth(admin)).json()
    actualizado = next(r for r in listado["releases"] if r["id"] == release_id)
    assert actualizado["color"] == "blanc"


def test_release_vinils_sin_extension_devuelve_none(db, client):
    admin = _admin_token(client, db)
    release = Release(artista="Artista Vinil", title="LP normal", formato="LP")
    db.add(release)
    db.commit()

    listado = client.get("/admin/releases", headers=_auth(admin)).json()
    r = next(x for x in listado["releases"] if x["id"] == str(release.id))
    assert r["color"] is None
    assert r["tipus_flor"] is None
    assert r["durabilitat_dies"] is None
