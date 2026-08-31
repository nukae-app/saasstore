"""Tests de la configuració general de la botiga (fila singleton)."""

import contextlib
import io
import re

from sqlalchemy import select

from app.models import ConfiguracioBotiga, User


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


def test_get_configuracio_admin(db, client):
    admin = _admin_token(client, db)
    resp = client.get("/admin/configuracio", headers=_auth(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 1
    assert body["reservation_minutes"] == 20


def test_patch_configuracio_admin(db, client):
    admin = _admin_token(client, db)
    resp = client.patch(
        "/admin/configuracio",
        json={"fiscal_name": "Nova Botiga SL", "nif": "B12345678", "phone": "931234567"},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["fiscal_name"] == "Nova Botiga SL"
    assert body["nif"] == "B12345678"
    assert body["phone"] == "931234567"


def test_get_configuracio_requereix_admin(client):
    resp = client.get("/admin/configuracio")
    assert resp.status_code in (401, 403)


def test_config_publica_no_exposa_nif(db, client):
    admin = _admin_token(client, db)
    client.patch(
        "/admin/configuracio",
        json={"nif": "B12345678", "phone": "931234567", "instagram_url": "https://instagram.com/x"},
        headers=_auth(admin),
    )

    resp = client.get("/config/public")
    assert resp.status_code == 200
    body = resp.json()
    assert "nif" not in body
    assert body["phone"] == "931234567"
    assert body["instagram_url"] == "https://instagram.com/x"


def test_reserva_minuts_es_desa(db, client):
    admin = _admin_token(client, db)
    resp = client.patch("/admin/configuracio", json={"reservation_minutes": 5}, headers=_auth(admin))
    assert resp.status_code == 200

    config = db.get(ConfiguracioBotiga, 1)
    assert config.reservation_minutes == 5


def test_legal_form_primer_cop_sembra_pla_de_comptes(db, client):
    """El tenant de test del fixture `db` ja té un pla de comptes sembrat a
    mà (per als tests de comptabilitat), però sense `legal_form` fixat —
    exactament l'estat dels tenants reals d'abans de la Fase 1. Esborrem
    aquest pla per simular un tenant net i comprovar que fixar legal_form
    per primera vegada el sembra sol."""
    from app.models import AccountingAccount

    db.query(AccountingAccount).delete()
    db.commit()

    admin = _admin_token(client, db)
    resp = client.patch("/admin/configuracio", json={"legal_form": "autonom"}, headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["legal_form"] == "autonom"

    codis = {a.code for a in db.query(AccountingAccount).all()}
    assert "550" in codis  # titular de l'explotació, autònom — no 100/112
    assert "100" not in codis


def test_legal_form_ja_fixat_dona_409(db, client):
    admin = _admin_token(client, db)
    # El fixture ja sembra el pla (ver conftest.py) però no fixa legal_form:
    # la primera crida l'estableix i re-sembra sense duplicar (el pla ja hi és).
    resp1 = client.patch("/admin/configuracio", json={"legal_form": "sl"}, headers=_auth(admin))
    assert resp1.status_code == 409  # ja_te_pla és True des del fixture

    from app.models import ConfiguracioBotiga
    config = db.get(ConfiguracioBotiga, 1)
    assert config.legal_form is None  # no s'ha tocat


def test_legal_form_invalid_per_jurisdiccio_dona_422(db, client):
    from app.models import AccountingAccount

    db.query(AccountingAccount).delete()
    db.commit()

    admin = _admin_token(client, db)
    resp = client.patch("/admin/configuracio", json={"legal_form": "ltd"}, headers=_auth(admin))
    assert resp.status_code == 422
