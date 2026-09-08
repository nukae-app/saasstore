"""Tests de la factura de venda (Bloc B2, capa base sense VeriFactu — veure
docstring de app/models/documents.py): creació manual (amb assentament
comptable), a partir d'una comanda web o d'un tiquet de TPV (sense
assentament nou, ja comptabilitzat en el seu moment), numeració, PDF i
anul·lació."""

import contextlib
import io
import re
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    CondicionItem, Item, JournalEntry, JournalLine, JournalSourceType, Order, OrderItem, Release, User,
)


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


def _factura_manual_payload(**overrides) -> dict:
    payload = {
        "client_name": "Estudi de gravació X",
        "client_nif": "B99999999",
        "lines": [{"description": "Servei de masterització", "quantity": "1", "unit_price": "200.00", "vat_pct": "21"}],
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Factura manual (des de zero)
# ---------------------------------------------------------------------------

def test_crear_factura_manual(client, db):
    admin = _admin_token(client, db)
    resp = client.post("/admin/factures", json=_factura_manual_payload(), headers=_auth(admin))
    assert resp.status_code == 201
    body = resp.json()
    assert body["origen"] == "manual"
    assert body["status"] == "emesa"
    assert body["number"] == 1
    assert body["fiscal_year"] == date.today().year
    assert body["client_nif"] == "B99999999"
    assert body["base_total"] == "200.00"
    assert body["vat_total"] == "42.00"
    assert body["total"] == "242.00"

    resp2 = client.post("/admin/factures", json=_factura_manual_payload(), headers=_auth(admin))
    assert resp2.json()["number"] == 2


def test_factura_manual_genera_assentament_a_705(client, db):
    admin = _admin_token(client, db)
    body = client.post("/admin/factures", json=_factura_manual_payload(), headers=_auth(admin)).json()

    entry = db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_type == JournalSourceType.factura_manual, JournalEntry.source_id == uuid.UUID(body["id"]),
        )
    )
    assert entry is not None
    lines = db.scalars(select(JournalLine).where(JournalLine.entry_id == entry.id)).all()
    assert sum(l.debit for l in lines) == sum(l.credit for l in lines) == Decimal("242.00")
    codis = {l.account.code: (l.debit, l.credit) for l in lines}
    assert codis["430"] == (Decimal("242.00"), Decimal("0.00"))
    assert codis["705"] == (Decimal("0.00"), Decimal("200.00"))
    assert codis["477"] == (Decimal("0.00"), Decimal("42.00"))


def test_factura_manual_pdf(client, db):
    admin = _admin_token(client, db)
    body = client.post("/admin/factures", json=_factura_manual_payload(), headers=_auth(admin)).json()
    resp = client.get(f"/admin/factures/{body['id']}/pdf", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


def test_anullar_factura_manual_reverteix_assentament(client, db):
    admin = _admin_token(client, db)
    body = client.post("/admin/factures", json=_factura_manual_payload(), headers=_auth(admin)).json()

    resp = client.post(f"/admin/factures/{body['id']}/anullar", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["status"] == "anullada"

    entry = db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_type == JournalSourceType.factura_manual, JournalEntry.source_id == uuid.UUID(body["id"]),
        )
    )
    assert entry is None  # revertit

    # No es pot anul·lar dos cops.
    resp2 = client.post(f"/admin/factures/{body['id']}/anullar", headers=_auth(admin))
    assert resp2.status_code == 409


def test_factura_anullada_no_reutilitza_el_numero(client, db):
    admin = _admin_token(client, db)
    f1 = client.post("/admin/factures", json=_factura_manual_payload(), headers=_auth(admin)).json()
    client.post(f"/admin/factures/{f1['id']}/anullar", headers=_auth(admin))

    f2 = client.post("/admin/factures", json=_factura_manual_payload(), headers=_auth(admin)).json()
    assert f2["number"] == 2  # no reutilitza l'1


# ---------------------------------------------------------------------------
# Factura des de comanda web (origen=ticket) — NO genera assentament nou
# ---------------------------------------------------------------------------

def _seed_order_amb_linia(db, preu="20.00") -> Order:
    release = Release(artista="Artista", title="Àlbum", formato="LP")
    db.add(release)
    db.flush()
    order = Order(
        contact_email="client@example.com", total=Decimal(preu), shipping_method="recogida_tienda",
        shipping_address={"recipient_name": "Joana Puig", "address_line1": "C. Wellington 12", "city": "Barcelona", "postal_code": "08005"},
    )
    db.add(order)
    db.flush()
    db.add(OrderItem(
        order_id=order.id, release_id=release.id, price=Decimal(preu),
        condition=CondicionItem.nou, quantity=1, vat_pct=Decimal("21.00"),
    ))
    db.commit()
    return order


def test_crear_factura_des_de_order(client, db):
    admin = _admin_token(client, db)
    order = _seed_order_amb_linia(db, preu="20.00")

    resp = client.post(f"/admin/factures/des-de-order/{order.id}?client_nif=B12345678", headers=_auth(admin))
    assert resp.status_code == 201
    body = resp.json()
    assert body["origen"] == "ticket"
    assert body["order_id"] == str(order.id)
    assert body["client_name"] == "Joana Puig"
    assert body["client_nif"] == "B12345678"
    assert len(body["lines"]) == 1
    assert body["lines"][0]["description"] == "Artista - Àlbum"
    assert body["total"] == "20.00"

    # No genera cap assentament (ja comptabilitzat via post_venda en el seu moment).
    entry = db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_type == JournalSourceType.factura_manual, JournalEntry.source_id == uuid.UUID(body["id"]),
        )
    )
    assert entry is None

    # Una comanda ja facturada no es pot tornar a facturar.
    resp2 = client.post(f"/admin/factures/des-de-order/{order.id}", headers=_auth(admin))
    assert resp2.status_code == 409


def test_factura_des_de_order_inexistent_dona_404(client, db):
    admin = _admin_token(client, db)
    resp = client.post(f"/admin/factures/des-de-order/{uuid.uuid4()}", headers=_auth(admin))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Factura des de tiquet de TPV (origen=ticket)
# ---------------------------------------------------------------------------

def _seed_venda_externa(client, token, db, *, preu="25.00") -> str:
    release = Release(artista="B", title="T2", formato="LP")
    db.add(release)
    db.commit()
    item = Item(release_id=release.id, price=Decimal(preu), acquisition_cost=Decimal("10.00"), condition=CondicionItem.nou, quantity=1)
    db.add(item)
    db.commit()
    resp = client.post(
        "/admin/ventas-externas",
        json={
            "item_id": str(item.id), "channel": "mostrador", "payment_method": "efectivo",
            "sale_price": preu, "quantity": 1, "date": "2026-04-01T10:00:00", "client_name": "Client mostrador X",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return resp.json()["ticket_id"]


def test_crear_factura_des_de_venda_externa(client, db):
    admin = _admin_token(client, db)
    ticket_id = _seed_venda_externa(client, admin, db, preu="25.00")

    resp = client.post(f"/admin/factures/des-de-venda-externa/{ticket_id}", headers=_auth(admin))
    assert resp.status_code == 201
    body = resp.json()
    assert body["origen"] == "ticket"
    assert body["client_name"] == "Client mostrador X"
    assert body["total"] == "25.00"

    entry = db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_type == JournalSourceType.factura_manual, JournalEntry.source_id == uuid.UUID(body["id"]),
        )
    )
    assert entry is None

    resp2 = client.post(f"/admin/factures/des-de-venda-externa/{ticket_id}", headers=_auth(admin))
    assert resp2.status_code == 409


def test_factura_des_de_tiquet_inexistent_dona_404(client, db):
    admin = _admin_token(client, db)
    resp = client.post(f"/admin/factures/des-de-venda-externa/{uuid.uuid4()}", headers=_auth(admin))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Numeració compartida amb pressupostos/albarans però independent per tipus
# ---------------------------------------------------------------------------

def test_numeracio_factura_independent_de_pressupostos(client, db):
    admin = _admin_token(client, db)
    client.post(
        "/admin/pressupostos",
        json={"client_name": "X", "lines": [{"description": "Y", "unit_price": "10.00"}]},
        headers=_auth(admin),
    )
    body = client.post("/admin/factures", json=_factura_manual_payload(), headers=_auth(admin)).json()
    assert body["number"] == 1  # comptador independent, no arrossega el de pressupostos
