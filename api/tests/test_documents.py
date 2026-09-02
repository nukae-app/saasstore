"""Tests del Bloc B1 (documents comercials no fiscals — veure
docs/PLAN_PARIDAD_HOLDED.md): pressupostos, albarans i factura de compra en PDF."""

import contextlib
import io
import re
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    CategoriaDespesa, CondicionItem, Despesa, EstatPagamentDespesa, Order, OrderItem, Release, User,
)
from app.services.documents_numbering import next_document_number


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


def _pressupost_payload(**overrides) -> dict:
    payload = {
        "client_name": "Client de prova",
        "client_email": "client@example.com",
        "lines": [{"description": "Vinil rar", "quantity": "2", "unit_price": "18.00", "vat_pct": "21"}],
    }
    payload.update(overrides)
    return payload


def test_next_document_number_es_correlatiu_i_independent_per_tipus_i_any(db):
    assert next_document_number(db, "pressupost", 2026) == 1
    assert next_document_number(db, "pressupost", 2026) == 2
    assert next_document_number(db, "pressupost", 2027) == 1
    assert next_document_number(db, "albara", 2026) == 1
    db.commit()


def test_crear_pressupost(client, db):
    admin = _admin_token(client, db)
    resp = client.post("/admin/pressupostos", json=_pressupost_payload(), headers=_auth(admin))
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "esborrany"
    assert body["number"] == 1
    assert body["fiscal_year"] == date.today().year
    assert len(body["lines"]) == 1
    assert body["lines"][0]["description"] == "Vinil rar"
    assert Decimal(body["lines"][0]["unit_price"]) == Decimal("18.00")

    resp2 = client.post("/admin/pressupostos", json=_pressupost_payload(), headers=_auth(admin))
    assert resp2.json()["number"] == 2


def test_editar_pressupost_nomes_en_esborrany(client, db):
    admin = _admin_token(client, db)
    p = client.post("/admin/pressupostos", json=_pressupost_payload(), headers=_auth(admin)).json()

    nou_payload = _pressupost_payload(client_name="Client nou")
    resp = client.patch(f"/admin/pressupostos/{p['id']}", json=nou_payload, headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["client_name"] == "Client nou"

    client.post(f"/admin/pressupostos/{p['id']}/rebutjar", headers=_auth(admin))
    resp2 = client.patch(f"/admin/pressupostos/{p['id']}", json=nou_payload, headers=_auth(admin))
    assert resp2.status_code == 409


def test_eliminar_pressupost_nomes_en_esborrany(client, db):
    admin = _admin_token(client, db)
    p = client.post("/admin/pressupostos", json=_pressupost_payload(), headers=_auth(admin)).json()
    client.post(f"/admin/pressupostos/{p['id']}/acceptar", headers=_auth(admin))

    resp = client.delete(f"/admin/pressupostos/{p['id']}", headers=_auth(admin))
    assert resp.status_code == 409


def test_flux_estats_pressupost(client, db):
    admin = _admin_token(client, db)
    p = client.post("/admin/pressupostos", json=_pressupost_payload(), headers=_auth(admin)).json()

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        resp = client.post(f"/admin/pressupostos/{p['id']}/enviar", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["status"] == "enviat"

    resp2 = client.post(f"/admin/pressupostos/{p['id']}/acceptar", headers=_auth(admin))
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "acceptat"

    # Un cop acceptat, ja no es pot rebutjar
    resp3 = client.post(f"/admin/pressupostos/{p['id']}/rebutjar", headers=_auth(admin))
    assert resp3.status_code == 409


def test_enviar_pressupost_sense_email_falla(client, db):
    admin = _admin_token(client, db)
    p = client.post(
        "/admin/pressupostos", json=_pressupost_payload(client_email=None), headers=_auth(admin)
    ).json()
    resp = client.post(f"/admin/pressupostos/{p['id']}/enviar", headers=_auth(admin))
    assert resp.status_code == 422


def test_pressupost_pdf(client, db):
    admin = _admin_token(client, db)
    p = client.post("/admin/pressupostos", json=_pressupost_payload(), headers=_auth(admin)).json()
    resp = client.get(f"/admin/pressupostos/{p['id']}/pdf", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


def _seed_order_amb_linia(db) -> Order:
    release = Release(artista="Artista", title="Àlbum", formato="LP")
    db.add(release)
    db.flush()
    order = Order(
        contact_email="client@example.com", total=Decimal("20.00"), shipping_method="recogida_tienda",
    )
    db.add(order)
    db.flush()
    db.add(OrderItem(
        order_id=order.id, release_id=release.id, price=Decimal("20.00"),
        condition=CondicionItem.nou, quantity=1,
    ))
    db.commit()
    return order


def test_crear_albara(client, db):
    admin = _admin_token(client, db)
    order = _seed_order_amb_linia(db)

    resp = client.post("/admin/albarans", json={"order_id": str(order.id)}, headers=_auth(admin))
    assert resp.status_code == 201
    body = resp.json()
    assert body["number"] == 1
    assert body["order_id"] == str(order.id)

    # Un mateix pedido no pot tenir dos albarans (v1, veure PLAN_PARIDAD_HOLDED.md B1)
    resp2 = client.post("/admin/albarans", json={"order_id": str(order.id)}, headers=_auth(admin))
    assert resp2.status_code == 409


def test_albara_pdf(client, db):
    admin = _admin_token(client, db)
    order = _seed_order_amb_linia(db)
    albara = client.post("/admin/albarans", json={"order_id": str(order.id)}, headers=_auth(admin)).json()

    resp = client.get(f"/admin/albarans/{albara['id']}/pdf", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_despesa_pdf(client, db):
    admin = _admin_token(client, db)
    despesa = Despesa(
        invoice_date=date(2026, 1, 15), supplier_name="Proveïdor SL", category=CategoriaDespesa.altres,
        concept="Material d'oficina", taxable_base=Decimal("50.00"), vat_pct=Decimal("21.00"),
        vat_amount=Decimal("10.50"), total=Decimal("60.50"), payment_status=EstatPagamentDespesa.pendent,
    )
    db.add(despesa)
    db.commit()

    resp = client.get(f"/admin/despeses/{despesa.id}/pdf", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"
