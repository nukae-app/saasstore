"""Cumplimiento legal del checkout: aceptación de condiciones (prueba, RGPD art. 7.1)
y función de desistimiento (Directiva 2011/83/UE art. 11 bis)."""

from decimal import Decimal

from sqlalchemy import select

from app.models import Item, Order, Release


def _compra(db, client, email="client@example.com"):
    r = Release(artista="Los Ganglios", title="Peruguay", formato="LP")
    db.add(r)
    db.flush()
    item = Item(release_id=r.id, price=Decimal("22.00"))
    db.add(item)
    db.commit()
    assert client.post("/cart/items", json={"item_id": str(item.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200
    return email


def _confirm(client, email, **extra):
    return client.post(
        "/checkout/confirm",
        json={"contact_email": email, "shipping_method": "recogida_tienda", **extra},
    )


def test_confirm_sense_acceptar_condicions_es_rebutja(db, client):
    email = _compra(db, client)
    res = _confirm(client, email, accept_terms=False)
    assert res.status_code == 422
    assert db.scalar(select(Order)) is None  # no s'ha creat cap comanda


def test_confirm_deixa_prova_de_l_acceptacio(db, client):
    email = _compra(db, client)
    res = _confirm(client, email)
    assert res.status_code == 201
    order = db.scalar(select(Order))
    assert order.terms_accepted_at is not None


def _comanda(db, client, email="client@example.com"):
    _confirm(client, _compra(db, client, email))
    return db.scalar(select(Order))


def test_desistiment_segella_la_comanda(db, client):
    order = _comanda(db, client)
    ref = str(order.id)[:8]
    res = client.post("/orders/withdrawal", json={"order_ref": ref, "email": "CLIENT@example.com"})
    assert res.status_code == 200 and res.json() == {"ok": True}
    db.refresh(order)
    assert order.withdrawal_requested_at is not None


def test_desistiment_amb_dades_que_no_coincideixen_no_revela_res(db, client):
    order = _comanda(db, client)
    ref = str(order.id)[:8]
    # email d'un altre client: mateixa resposta, cap canvi
    res = client.post("/orders/withdrawal", json={"order_ref": ref, "email": "altre@example.com"})
    assert res.status_code == 200 and res.json() == {"ok": True}
    db.refresh(order)
    assert order.withdrawal_requested_at is None
    # referència inexistent: igual
    res = client.post("/orders/withdrawal", json={"order_ref": "00000000", "email": "client@example.com"})
    assert res.status_code == 200 and res.json() == {"ok": True}


def test_desistiment_es_idempotent(db, client):
    order = _comanda(db, client)
    ref = str(order.id)[:8]
    body = {"order_ref": ref, "email": "client@example.com"}
    client.post("/orders/withdrawal", json=body)
    db.refresh(order)
    primera = order.withdrawal_requested_at
    client.post("/orders/withdrawal", json=body)
    db.refresh(order)
    assert order.withdrawal_requested_at == primera  # la data original no es reescriu
