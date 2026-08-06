"""Tests del CRUD de marges configurables (suggeriment de preu a la recepció)."""

import contextlib
import io
import re

from sqlalchemy import select

from app.models import MargeConfig, User


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
    user.rol = "admin"
    db.commit()
    return access


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_crud_marge(db, client):
    admin = _admin_token(client, db)

    resp = client.post(
        "/admin/marges",
        json={"nom": "Marge estàndard nou", "percentatge": "40.00", "per_defecte_nou": True},
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    marge_id = resp.json()["id"]

    resp = client.get("/admin/marges", headers=_auth(admin))
    assert resp.status_code == 200
    assert any(m["id"] == marge_id for m in resp.json())

    resp = client.patch(f"/admin/marges/{marge_id}", json={"percentatge": "50.00"}, headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["percentatge"] == "50.00"


def test_nomes_un_marge_per_defecte_nou_actiu(db, client):
    """Marcar un segon marge com a per_defecte_nou desmarca l'anterior."""
    admin = _admin_token(client, db)
    m1 = client.post(
        "/admin/marges",
        json={"nom": "A", "percentatge": "40.00", "per_defecte_nou": True},
        headers=_auth(admin),
    ).json()
    m2 = client.post(
        "/admin/marges",
        json={"nom": "B", "percentatge": "60.00", "per_defecte_nou": True},
        headers=_auth(admin),
    ).json()

    assert db.get(MargeConfig, m1["id"]).per_defecte_nou is False
    assert db.get(MargeConfig, m2["id"]).per_defecte_nou is True


def test_nomes_un_marge_per_defecte_segona_ma_actiu(db, client):
    admin = _admin_token(client, db)
    m1 = client.post(
        "/admin/marges",
        json={"nom": "A", "percentatge": "40.00", "per_defecte_segona_ma": True},
        headers=_auth(admin),
    ).json()
    m2 = client.post(
        "/admin/marges",
        json={"nom": "B", "percentatge": "60.00", "per_defecte_segona_ma": True},
        headers=_auth(admin),
    ).json()

    assert db.get(MargeConfig, m1["id"]).per_defecte_segona_ma is False
    assert db.get(MargeConfig, m2["id"]).per_defecte_segona_ma is True


def test_list_marges_nomes_actius(db, client):
    admin = _admin_token(client, db)
    actiu = client.post(
        "/admin/marges", json={"nom": "Actiu", "percentatge": "40.00"}, headers=_auth(admin)
    ).json()
    client.post(
        "/admin/marges", json={"nom": "Inactiu", "percentatge": "30.00", "actiu": False}, headers=_auth(admin)
    )

    resp = client.get("/admin/marges", params={"nomes_actius": True}, headers=_auth(admin))
    assert resp.status_code == 200
    ids = [m["id"] for m in resp.json()]
    assert actiu["id"] in ids
    assert all(m["actiu"] for m in resp.json())
