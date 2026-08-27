"""Tests de l'autoservei de subscripció del client (/me/subscripcio):
consultar l'estat, pausar/reprendre, canviar seccions/adreça i cancel·lar."""

import contextlib
import io
import re
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    Address, Assignacio, CobramentSubscripcio, EstatAssignacio, EstatCobrament,
    EstatSubscripcio, Item, ItemStatus, Release, Subscripcio, User,
)


def _login(client, email):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _seed_subscripcio(db, user_id, address_id) -> Subscripcio:
    sub = Subscripcio(
        user_id=user_id, address_id=address_id, estat=EstatSubscripcio.activa,
        periodicitat_mesos=1, quantitat=1, preu_periode=Decimal("25.00"),
        redsys_identifier="T", proxima_facturacio=date.today(),
    )
    db.add(sub)
    db.commit()
    return sub


def test_get_subscripcio_inclou_historic_de_discos_rebuts(db, client):
    access = _login(client, "fan@example.com")
    user = db.scalar(select(User).where(User.email == "fan@example.com"))
    address = Address(user_id=user.id, recipient_name="Fan", address_line1="C", city="BCN", postal_code="08001")
    db.add(address)
    db.commit()
    sub = _seed_subscripcio(db, user.id, address.id)

    release = Release(artista="A", title="B", formato="LP")
    db.add(release)
    db.flush()
    item = Item(release_id=release.id, price=Decimal("20.00"), status=ItemStatus.vendido)
    db.add(item)
    cobrament = CobramentSubscripcio(
        subscripcio_id=sub.id, periode=date.today(), import_=Decimal("25.00"),
        estat=EstatCobrament.cobrat, ds_order="abc123456789",
    )
    db.add(cobrament)
    db.flush()
    db.add(Assignacio(
        cobrament_id=cobrament.id, subscripcio_id=sub.id, item_id=item.id, release_id=release.id,
        estat=EstatAssignacio.confirmada,
    ))
    db.commit()

    headers = {"Authorization": f"Bearer {access}"}
    r = client.get("/me/subscripcio", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["estat"] == "activa"
    assert body["quantitat"] == 1
    assert body["preu_periode"] == "25.00"
    assert len(body["discos_rebuts"]) == 1
    assert body["discos_rebuts"][0]["titulo"] == "B"


def test_pausar_reprendre_i_cancelar(db, client):
    access = _login(client, "fan2@example.com")
    user = db.scalar(select(User).where(User.email == "fan2@example.com"))
    address = Address(user_id=user.id, recipient_name="Fan", address_line1="C", city="BCN", postal_code="08001")
    db.add(address)
    db.commit()
    _seed_subscripcio(db, user.id, address.id)

    headers = {"Authorization": f"Bearer {access}"}

    pausa = client.patch("/me/subscripcio", json={"estat": "pausada"}, headers=headers)
    assert pausa.status_code == 200 and pausa.json()["estat"] == "pausada"

    reprendre = client.patch("/me/subscripcio", json={"estat": "activa"}, headers=headers)
    assert reprendre.status_code == 200 and reprendre.json()["estat"] == "activa"

    cancel = client.post("/me/subscripcio/cancelar", headers=headers)
    assert cancel.status_code == 200 and cancel.json()["estat"] == "cancel_lada"

    # un cop cancel·lada, ja no es considera "la subscripció" del client
    assert client.get("/me/subscripcio", headers=headers).status_code == 404


def test_no_es_pot_canviar_una_adreca_d_un_altre_usuari(db, client):
    access = _login(client, "fan3@example.com")
    user = db.scalar(select(User).where(User.email == "fan3@example.com"))
    address = Address(user_id=user.id, recipient_name="Fan", address_line1="C", city="BCN", postal_code="08001")
    db.add(address)
    db.commit()
    _seed_subscripcio(db, user.id, address.id)

    altre = User(email="altre@example.com", name="Altre")
    db.add(altre)
    db.flush()
    adreca_aliena = Address(user_id=altre.id, recipient_name="Altre", address_line1="C2", city="BCN", postal_code="08002")
    db.add(adreca_aliena)
    db.commit()

    headers = {"Authorization": f"Bearer {access}"}
    r = client.patch("/me/subscripcio", json={"address_id": str(adreca_aliena.id)}, headers=headers)
    assert r.status_code == 404
