"""Derechos RGPD: exportación de datos (art. 15/20) y supresión completa (art. 17),
tanto por autoservicio (/me) como desde el admin."""

import contextlib
import io
import re
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    Address, AuthToken, Cart, EstadoPeticionCliente, EstatSubscripcio, Identity, NewsletterCampaign,
    NewsletterSend, Order, OrderStatus, PeticionCliente, RefreshToken, Subscripcio, User,
)


def _login(client, email):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _seed(db, email="clienta@example.com"):
    user = db.scalar(select(User).where(User.email == email))
    user.name, user.phone, user.consent_newsletter = "Clienta Real", "600111222", True
    user.internal_notes = "va fer una reclamació"
    addr = Address(user_id=user.id, recipient_name="Clienta Real", address_line1="Carrer Major 1",
                   city="BCN", postal_code="08001", phone="600111222")
    db.add_all([addr, Identity(user_id=user.id, provider="google", provider_user_id="g-123")])
    order = Order(user_id=user.id, contact_email=email, status=OrderStatus.entregado, total=Decimal("20"),
                  shipping_method="envio", shipping_address={"name": "Clienta Real", "line1": "Carrer Major 1"})
    db.add(order)
    camp = NewsletterCampaign(subject="Novetats", content_html="x")
    db.add(camp)
    db.flush()
    db.add(NewsletterSend(campaign_id=camp.id, user_id=user.id, email=email, unsubscribe_token_hash="h"))
    db.add(PeticionCliente(user_id=user.id, free_artist="X", free_title="Y", client_notes="trucar-me al 600111222",
                           status=EstadoPeticionCliente.cancelada))
    db.commit()
    return user, addr, order


def test_export_inclou_les_dades_i_cap_secret(client, db):
    headers = _login(client, "clienta@example.com")
    _seed(db)
    r = client.get("/me/data-export", headers=headers)
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    body = r.json()
    assert body["profile"]["email"] == "clienta@example.com"
    assert body["profile"]["phone"] == "600111222"
    assert body["addresses"][0]["address_line1"] == "Carrer Major 1"
    assert body["orders"][0]["shipping_address"]["line1"] == "Carrer Major 1"
    assert body["login_methods"]["linked_providers"][0]["provider"] == "google"
    assert body["newsletter"]["received"][0]["campaign"] == "Novetats"
    raw = r.text
    assert "password_hash" not in raw and "token_hash" not in raw and "g-123" not in raw


def test_export_requereix_sessio(client):
    assert client.get("/me/data-export").status_code == 401


def test_esborrar_compte_anonimitza_i_conserva_comandes(client, db):
    headers = _login(client, "clienta@example.com")
    user, addr, order = _seed(db)
    user_id, order_id = user.id, order.id

    r = client.request("DELETE", "/me", json={"confirm_email": "CLIENTA@example.com"}, headers=headers)
    assert r.status_code == 204

    db.expire_all()
    u = db.get(User, user_id)
    assert u.email.startswith("anon-") and u.email.endswith("@deleted.local")
    assert (u.name, u.phone, u.internal_notes, u.password_hash) == (None, None, None, None)
    assert u.active is False and u.consent_newsletter is False
    assert db.scalars(select(Address).where(Address.user_id == user_id)).all() == []
    assert db.scalars(select(Identity).where(Identity.user_id == user_id)).all() == []
    assert db.scalars(select(RefreshToken).where(RefreshToken.user_id == user_id)).all() == []
    assert db.scalars(select(AuthToken).where(AuthToken.email == "clienta@example.com")).all() == []
    assert db.scalar(select(Cart).where(Cart.user_id == user_id)) is None
    send = db.scalar(select(NewsletterSend))
    assert send.email == u.email
    pet = db.scalar(select(PeticionCliente))
    assert pet.client_notes is None
    o = db.get(Order, order_id)  # el pedido se conserva (obligación fiscal)...
    assert o.shipping_address["line1"] == "Carrer Major 1"
    assert o.contact_email == u.email  # ...pero sin el email real


def test_la_sessio_no_sobreviu_a_l_esborrat(client, db):
    headers = _login(client, "clienta@example.com")
    _seed(db)
    assert client.request("DELETE", "/me", json={"confirm_email": "clienta@example.com"}, headers=headers).status_code == 204
    assert client.post("/auth/refresh").status_code == 401
    assert client.get("/me/profile", headers=headers).status_code == 401


def test_esborrar_compte_exigeix_email_correcte(client, db):
    headers = _login(client, "clienta@example.com")
    r = client.request("DELETE", "/me", json={"confirm_email": "altre@example.com"}, headers=headers)
    assert r.status_code == 422
    assert db.scalar(select(User).where(User.email == "clienta@example.com")).active is True


def test_esborrar_compte_amb_contrasenya_la_exigeix(client, db):
    client.post("/auth/register", json={"email": "pw@example.com", "password": "contrasenya123"})
    user = db.scalar(select(User).where(User.email == "pw@example.com"))
    user.email_verified, user.active = True, True
    db.commit()
    access = client.post("/auth/login", json={"email": "pw@example.com", "password": "contrasenya123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    r = client.request("DELETE", "/me", json={"confirm_email": "pw@example.com"}, headers=headers)
    assert r.status_code == 403
    r = client.request("DELETE", "/me", json={"confirm_email": "pw@example.com", "password": "contrasenya123"}, headers=headers)
    assert r.status_code == 204


def test_no_es_pot_esborrar_amb_comanda_en_curs(client, db):
    headers = _login(client, "clienta@example.com")
    _, _, order = _seed(db)
    order.status = OrderStatus.pagado
    db.commit()
    r = client.request("DELETE", "/me", json={"confirm_email": "clienta@example.com"}, headers=headers)
    assert r.status_code == 409
    assert "open_orders" in r.json()["reasons"]
    assert db.scalar(select(User).where(User.email == "clienta@example.com")).active is True


def test_subscripcio_activa_bloqueja_i_force_la_cancela_sense_trencar_la_fk(client, db):
    headers = _login(client, "clienta@example.com")
    user, addr, _ = _seed(db)
    sub = Subscripcio(user_id=user.id, address_id=addr.id, estat=EstatSubscripcio.activa, periodicitat_mesos=1,
                      quantitat=1, preu_periode=Decimal("25"), redsys_identifier="TOKEN", proxima_facturacio=date.today())
    db.add(sub)
    db.commit()
    assert client.request("DELETE", "/me", json={"confirm_email": "clienta@example.com"}, headers=headers).status_code == 409

    admin = _login(client, "admin@example.com")
    db.scalar(select(User).where(User.email == "admin@example.com")).role = "admin"
    db.commit()
    r = client.post(f"/admin/users/{user.id}/anonymize?force=true", headers=admin)
    assert r.status_code == 200, r.text

    db.expire_all()
    sub = db.get(Subscripcio, sub.id)
    assert sub.estat == EstatSubscripcio.cancel_lada and sub.redsys_identifier is None
    a = db.get(Address, addr.id)  # RESTRICT: la fila sigue, pero vaciada
    assert a.address_line1 == "—" and a.phone is None


def test_admin_no_pot_anonimitzar_un_admin(client, db):
    admin = _login(client, "admin@example.com")
    me = db.scalar(select(User).where(User.email == "admin@example.com"))
    me.role = "admin"
    db.commit()
    r = client.post(f"/admin/users/{me.id}/anonymize?force=true", headers=admin)
    assert r.status_code == 409 and r.json()["reasons"] == ["is_admin"]
