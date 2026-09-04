"""Tests del flux de peticions de client: crear -> admin posa preu -> client
accepta/rebutja -> admin la vincula a una SolicitudCompra."""

import contextlib
import io
import re
import uuid

from sqlalchemy import select

from app.models import CondicionItem, Item, ItemStatus, PeticionCliente, Release, StockHold, User


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


def _seed_release(db, artista="Artista", titulo="Àlbum") -> Release:
    r = Release(artista=artista, title=titulo, formato="LP")
    db.add(r)
    db.commit()
    return r


def test_crear_peticion_release_sense_estoc(db, client):
    token = _login(client, "client@example.com")
    release = _seed_release(db)

    resp = client.post("/me/peticiones", json={"release_id": str(release.id)}, headers=_auth(token))
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pendent"
    assert body["artista"] == "Artista"


def test_crear_peticion_release_amb_estoc_falla(db, client):
    token = _login(client, "client@example.com")
    release = _seed_release(db)
    db.add(Item(release_id=release.id, price=25, condition=CondicionItem.nou, status=ItemStatus.disponible))
    db.commit()

    resp = client.post("/me/peticiones", json={"release_id": str(release.id)}, headers=_auth(token))
    assert resp.status_code == 409


def test_crear_peticion_text_lliure(db, client):
    token = _login(client, "client@example.com")
    resp = client.post(
        "/me/peticiones",
        json={"free_artist": "Grup Desconegut", "free_title": "Disc Rar"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["release_id"] is None
    assert body["artista"] == "Grup Desconegut"


def test_crear_peticion_sense_release_ni_text_falla(db, client):
    token = _login(client, "client@example.com")
    resp = client.post("/me/peticiones", json={}, headers=_auth(token))
    assert resp.status_code == 422


def test_flux_complet_fins_en_tramit(db, client):
    client_token = _login(client, "client@example.com")
    admin_token = _admin_token(client, db)
    release = _seed_release(db)

    peticion = client.post(
        "/me/peticiones", json={"release_id": str(release.id)}, headers=_auth(client_token)
    ).json()
    peticion_id = peticion["id"]

    # Admin fixa preu -> notifica -> pendent_acceptacio
    resp = client.patch(
        f"/admin/peticiones/{peticion_id}/precio",
        json={"estimated_price": "28.00"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "pendent_acceptacio"

    resp = client.post(
        f"/me/peticiones/{peticion_id}/aceptar",
        json={"metodo_entrega": "recollida_paga_botiga"},
        headers=_auth(client_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "acceptada"
    assert resp.json()["chosen_delivery_method"] == "recollida_paga_botiga"

    resp = client.post(
        f"/admin/peticiones/{peticion_id}/vincular-solicitud",
        json={"cantidad": 1},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    linea = resp.json()
    assert linea["origen"] == "peticion_cliente"

    db.expire_all()
    peticion_db = db.get(PeticionCliente, uuid.UUID(peticion_id))
    assert peticion_db.status.value == "en_tramit"
    assert peticion_db.solicitud_compra_linea_id is not None


def test_rebutjar_peticion(db, client):
    client_token = _login(client, "client@example.com")
    admin_token = _admin_token(client, db)
    release = _seed_release(db)

    peticion = client.post(
        "/me/peticiones", json={"release_id": str(release.id)}, headers=_auth(client_token)
    ).json()
    client.patch(
        f"/admin/peticiones/{peticion['id']}/precio",
        json={"estimated_price": "28.00"},
        headers=_auth(admin_token),
    )

    resp = client.post(f"/me/peticiones/{peticion['id']}/rechazar", headers=_auth(client_token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "rebutjada"

    resp2 = client.post(
        f"/me/peticiones/{peticion['id']}/aceptar",
        json={"metodo_entrega": "envio"},
        headers=_auth(client_token),
    )
    assert resp2.status_code == 409


def test_vincular_solicitud_sense_acceptar_falla(db, client):
    client_token = _login(client, "client@example.com")
    admin_token = _admin_token(client, db)
    release = _seed_release(db)

    peticion = client.post(
        "/me/peticiones", json={"release_id": str(release.id)}, headers=_auth(client_token)
    ).json()

    resp = client.post(
        f"/admin/peticiones/{peticion['id']}/vincular-solicitud",
        json={"cantidad": 1},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 409


def test_catalogar_peticion_text_lliure(db, client):
    client_token = _login(client, "client@example.com")
    admin_token = _admin_token(client, db)
    release = _seed_release(db, artista="Nou Grup", titulo="Nou Disc")

    peticion = client.post(
        "/me/peticiones",
        json={"free_artist": "Nou Grup", "free_title": "Nou Disc"},
        headers=_auth(client_token),
    ).json()
    assert peticion["release_id"] is None

    resp = client.patch(
        f"/admin/peticiones/{peticion['id']}/catalogar",
        json={"release_id": str(release.id)},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["release_id"] == str(release.id)


def test_canviar_disc_amb_preu_ja_fixat_reseteja_a_pendent(db, client):
    admin_token = _admin_token(client, db)
    client_token = _login(client, "client@example.com")
    release_mal = _seed_release(db, artista="Grup Erroni", titulo="Disc Erroni")
    release_bo = _seed_release(db, artista="Grup Correcte", titulo="Disc Correcte")

    peticion = client.post(
        "/me/peticiones",
        json={"free_artist": "Grup Correcte", "free_title": "Disc Correcte"},
        headers=_auth(client_token),
    ).json()
    client.patch(
        f"/admin/peticiones/{peticion['id']}/catalogar",
        json={"release_id": str(release_mal.id)},
        headers=_auth(admin_token),
    )
    resp = client.patch(
        f"/admin/peticiones/{peticion['id']}/precio",
        json={"estimated_price": "28.00"},
        headers=_auth(admin_token),
    )
    assert resp.json()["status"] == "pendent_acceptacio"

    resp = client.patch(
        f"/admin/peticiones/{peticion['id']}/catalogar",
        json={"release_id": str(release_bo.id)},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["release_id"] == str(release_bo.id)
    assert body["status"] == "pendent"
    assert body["estimated_price"] is None


def test_canviar_disc_despres_acceptada_falla(db, client):
    client_token, admin_token, release = _peticion_en_tramit(client, db, "recollida_paga_botiga")
    peticion_id = str(db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id)
    altre_release = _seed_release(db, artista="Un altre", titulo="Un altre disc")

    resp = client.patch(
        f"/admin/peticiones/{peticion_id}/catalogar",
        json={"release_id": str(altre_release.id)},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 409


def test_no_es_aquest_torna_a_pendent_amb_comentari(db, client):
    admin_token = _admin_token(client, db)
    client_token = _login(client, "client@example.com")
    release = _seed_release(db)

    peticion = client.post(
        "/me/peticiones", json={"release_id": str(release.id)}, headers=_auth(client_token)
    ).json()
    client.patch(
        f"/admin/peticiones/{peticion['id']}/precio",
        json={"estimated_price": "28.00"},
        headers=_auth(admin_token),
    )

    resp = client.post(
        f"/me/peticiones/{peticion['id']}/no-es-aquest",
        json={"comentari": "Era l'edició en directe, no l'estudi"},
        headers=_auth(client_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pendent"
    assert body["estimated_price"] is None

    db.expire_all()
    peticion_db = db.get(PeticionCliente, uuid.UUID(peticion["id"]))
    assert "Era l'edició en directe" in peticion_db.client_notes

    resp_admin = client.get("/admin/peticiones", headers=_auth(admin_token))
    p_out = next(p for p in resp_admin.json() if p["id"] == peticion["id"])
    assert "Era l'edició en directe" in p_out["client_notes"]


def test_no_es_aquest_fora_de_pendent_acceptacio_falla(db, client):
    client_token = _login(client, "client@example.com")
    release = _seed_release(db)
    peticion = client.post(
        "/me/peticiones", json={"release_id": str(release.id)}, headers=_auth(client_token)
    ).json()

    resp = client.post(
        f"/me/peticiones/{peticion['id']}/no-es-aquest",
        json={"comentari": "..."},
        headers=_auth(client_token),
    )
    assert resp.status_code == 409


def test_cancelar_peticion_propia(db, client):
    token = _login(client, "client@example.com")
    release = _seed_release(db)
    peticion = client.post(
        "/me/peticiones", json={"release_id": str(release.id)}, headers=_auth(token)
    ).json()

    resp = client.delete(f"/me/peticiones/{peticion['id']}", headers=_auth(token))
    assert resp.status_code == 204

    db.expire_all()
    assert db.get(PeticionCliente, uuid.UUID(peticion["id"])).status.value == "cancelada"


def test_no_es_pot_veure_peticio_d_un_altre_client(db, client):
    token_a = _login(client, "clienta@example.com")
    token_b = _login(client, "clientb@example.com")
    release = _seed_release(db)

    peticion = client.post(
        "/me/peticiones", json={"release_id": str(release.id)}, headers=_auth(token_a)
    ).json()

    resp = client.delete(f"/me/peticiones/{peticion['id']}", headers=_auth(token_b))
    assert resp.status_code == 404


def test_admin_llista_i_filtra_per_estat(db, client):
    client_token = _login(client, "client@example.com")
    admin_token = _admin_token(client, db)
    release = _seed_release(db)
    client.post("/me/peticiones", json={"release_id": str(release.id)}, headers=_auth(client_token))

    resp = client.get("/admin/peticiones?estado=pendent", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert all(p["status"] == "pendent" for p in resp.json())
    assert len(resp.json()) == 1


_ADRECA_TEST = {
    "recipient_name": "Client Test", "address_line1": "Carrer Fals 1",
    "postal_code": "08001", "city": "Barcelona", "country": "ES",
}


def _peticion_en_tramit(client, db, metodo_entrega: str) -> tuple[str, str, Release]:
    """Helper: crea una petició i la porta fins a en_tramit amb el mètode donat."""
    client_token = _login(client, "client@example.com")
    admin_token = _admin_token(client, db)
    release = _seed_release(db)

    peticion = client.post(
        "/me/peticiones", json={"release_id": str(release.id)}, headers=_auth(client_token)
    ).json()
    client.patch(
        f"/admin/peticiones/{peticion['id']}/precio",
        json={"estimated_price": "28.00"},
        headers=_auth(admin_token),
    )
    aceptar_payload = {"metodo_entrega": metodo_entrega}
    if metodo_entrega == "envio":
        aceptar_payload["direccion_envio"] = _ADRECA_TEST
    resp = client.post(
        f"/me/peticiones/{peticion['id']}/aceptar",
        json=aceptar_payload,
        headers=_auth(client_token),
    )
    assert resp.status_code == 200, resp.json()
    client.post(
        f"/admin/peticiones/{peticion['id']}/vincular-solicitud",
        json={"cantidad": 1},
        headers=_auth(admin_token),
    )
    return client_token, admin_token, release


def test_vincular_item_recollida_paga_botiga_reserva_72h(db, client):
    """Nou (stock agregado): vincular-item retiene 1 unidad vía StockHold en
    vez de status/reserved_for_peticion_id (eso queda solo para segona_ma)."""
    client_token, admin_token, release = _peticion_en_tramit(client, db, "recollida_paga_botiga")
    peticion_id = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id

    item = Item(release_id=release.id, price=28, condition=CondicionItem.nou, quantity=1)
    db.add(item)
    db.commit()

    resp = client.post(
        f"/admin/peticiones/{peticion_id}/vincular-item",
        json={"item_id": str(item.id)},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "reservada"

    db.expire_all()
    item_db = db.get(Item, item.id)
    assert item_db.reserved_quantity == 1
    hold = db.scalar(select(StockHold).where(StockHold.item_id == item.id))
    assert hold is not None
    assert hold.peticion_id == uuid.UUID(str(peticion_id))
    assert hold.reserved_until is not None


def test_vincular_item_envio_sense_caducitat(db, client):
    client_token, admin_token, release = _peticion_en_tramit(client, db, "envio")
    peticion_id = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id

    item = Item(release_id=release.id, price=28, condition=CondicionItem.nou, quantity=1)
    db.add(item)
    db.commit()

    resp = client.post(
        f"/admin/peticiones/{peticion_id}/vincular-item",
        json={"item_id": str(item.id)},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200

    db.expire_all()
    item_db = db.get(Item, item.id)
    assert item_db.reserved_quantity == 1
    hold = db.scalar(select(StockHold).where(StockHold.item_id == item.id))
    assert hold is not None
    assert hold.reserved_until is None


def test_vincular_item_tanca_linia_i_solicitud(db, client):
    """Regressió: el fallback manual "Vincular exemplar" ha de tancar
    també la línia/sol·licitud de compra associada, si no es queda oberta
    per sempre encara que la petició ja s'hagi reservat (aquest era
    exactament el cas de Rosalía - Motomami)."""
    client_token, admin_token, release = _peticion_en_tramit(client, db, "envio")
    peticion_id = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id
    peticion_db = db.get(PeticionCliente, uuid.UUID(str(peticion_id)))
    linea_id = peticion_db.solicitud_compra_linea_id

    item = Item(release_id=release.id, price=28, condition=CondicionItem.nou, status=ItemStatus.disponible)
    db.add(item)
    db.commit()

    resp = client.post(
        f"/admin/peticiones/{peticion_id}/vincular-item",
        json={"item_id": str(item.id)},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200

    db.expire_all()
    from app.models import SolicitudCompraLinea

    linea_db = db.get(SolicitudCompraLinea, linea_id)
    assert linea_db.item_resuelto_id == item.id
    # Encara al pool (mai consolidada en cap sol·licitud numerada): resoldre
    # des d'estoc no en requereix una.
    assert linea_db.solicitud_id is None


def test_resoldre_estoc_reserva_per_peticio_i_tanca_solicitud(db, client):
    client_token, admin_token, release = _peticion_en_tramit(client, db, "recollida_paga_botiga")
    peticion_id = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id
    peticion_db = db.get(PeticionCliente, uuid.UUID(str(peticion_id)))
    linea_id = peticion_db.solicitud_compra_linea_id

    item = Item(release_id=release.id, price=28, condition=CondicionItem.segona_ma, status=ItemStatus.disponible)
    db.add(item)
    db.commit()

    resp = client.post(
        f"/admin/solicitudes-compra/lineas/{linea_id}/resoldre-estoc",
        json={"item_id": str(item.id)},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["resuelta"] is True

    db.expire_all()
    assert db.get(PeticionCliente, uuid.UUID(str(peticion_id))).status.value == "reservada"
    item_db = db.get(Item, item.id)
    assert item_db.status.value == "reservado"
    assert item_db.reserved_until is not None  # recollida_paga_botiga: 72h


def _resolver_solicitud_en_comanda(client, db, admin_token, peticion_id) -> str:
    from app.models import Proveedor, SolicitudCompraLinea

    peticion_db = db.get(PeticionCliente, uuid.UUID(peticion_id))
    linea_id = peticion_db.solicitud_compra_linea_id

    prov = Proveedor(name="Distri Test")
    db.add(prov)
    db.commit()

    # La línia encara és al pool (vincular-solicitud ja no crea cap
    # SolicitudCompra): cal consolidar-la primer.
    gen = client.post(
        "/admin/solicitudes-compra/generar",
        json={"linea_ids": [str(linea_id)]},
        headers=_auth(admin_token),
    )
    assert gen.status_code == 201, gen.text

    resp = client.post(
        "/admin/solicitudes-compra/resolver",
        json={
            "proveedor_id": str(prov.id),
            "date": "2026-06-01T10:00:00",
            "lineas": [{"solicitud_linea_id": str(linea_id), "estimated_unit_price": "20.00"}],
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    comanda_id = resp.json()["id"]

    db.expire_all()
    sol_linea = db.get(SolicitudCompraLinea, linea_id)
    assert sol_linea.comanda_linea_id is not None
    return comanda_id


def test_recepcio_reserva_automaticament_per_peticion_recollida_botiga(db, client):
    client_token, admin_token, release = _peticion_en_tramit(client, db, "recollida_paga_botiga")
    peticion_id = str(db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id)

    comanda_id = _resolver_solicitud_en_comanda(client, db, admin_token, peticion_id)

    from app.models import Comanda, EstadoComanda
    comanda = db.get(Comanda, uuid.UUID(comanda_id))
    comanda.status = EstadoComanda.enviada
    db.commit()
    linea_id = str(comanda.lineas[0].id)

    resp = client.post(
        f"/admin/comandas/{comanda_id}/recepcio",
        json={"date": "2026-06-10T10:00:00", "items": [{"comanda_linea_id": linea_id, "price": "28.00"}]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201

    db.expire_all()
    peticion_db = db.get(PeticionCliente, uuid.UUID(peticion_id))
    assert peticion_db.status.value == "reservada"
    assert peticion_db.item_id is not None

    # RecepcionItemIn.condicion por defecto es "nou": stock agregado, la
    # reserva de la petición es vía StockHold (no status/reserved_until en Item).
    item_db = db.get(Item, peticion_db.item_id)
    assert item_db.condition == CondicionItem.nou
    assert item_db.quantity == 1
    assert item_db.reserved_quantity == 1
    hold = db.scalar(select(StockHold).where(StockHold.peticion_id == uuid.UUID(peticion_id)))
    assert hold is not None
    assert hold.reserved_until is not None


def test_recepcio_reserva_automaticament_per_peticion_envio_sense_caducitat(db, client):
    client_token, admin_token, release = _peticion_en_tramit(client, db, "envio")
    peticion_id = str(db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id)

    comanda_id = _resolver_solicitud_en_comanda(client, db, admin_token, peticion_id)

    from app.models import Comanda, EstadoComanda
    comanda = db.get(Comanda, uuid.UUID(comanda_id))
    comanda.status = EstadoComanda.enviada
    db.commit()
    linea_id = str(comanda.lineas[0].id)

    resp = client.post(
        f"/admin/comandas/{comanda_id}/recepcio",
        json={"date": "2026-06-10T10:00:00", "items": [{"comanda_linea_id": linea_id, "price": "28.00"}]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201

    db.expire_all()
    peticion_db = db.get(PeticionCliente, uuid.UUID(peticion_id))
    assert peticion_db.status.value == "reservada"

    item_db = db.get(Item, peticion_db.item_id)
    assert item_db.reserved_quantity == 1
    hold = db.scalar(select(StockHold).where(StockHold.peticion_id == uuid.UUID(peticion_id)))
    assert hold is not None
    assert hold.reserved_until is None


def test_comprar_via1_afegeix_al_carret(db, client):
    client_token, admin_token, release = _peticion_en_tramit(client, db, "envio")
    peticion_id = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id

    item = Item(release_id=release.id, price=28, condition=CondicionItem.segona_ma, status=ItemStatus.disponible)
    db.add(item)
    db.commit()
    client.post(
        f"/admin/peticiones/{peticion_id}/vincular-item",
        json={"item_id": str(item.id)},
        headers=_auth(admin_token),
    )

    resp = client.post(f"/me/peticiones/{peticion_id}/comprar", headers=_auth(client_token))
    assert resp.status_code == 200

    db.expire_all()
    item_db = db.get(Item, item.id)
    assert item_db.status.value == "reservado"
    assert item_db.reserved_for_peticion_id is None
    assert item_db.reserved_by_cart_id is not None


def test_via1_reserva_carret_caducada_marca_peticio_caducada(db, client):
    """Regressió: si el client fa 'Comprar ara' (Via 1) però no acaba el
    checkout dins dels 15 minuts, l'exemplar torna a disponible i la petició
    NO s'ha de quedar zombi en estat 'reservada' per sempre — release_expired
    l'ha de detectar via item_id, no via reserved_for_peticion_id (que ja
    s'ha buidat en transferir la reserva al carret)."""
    from datetime import datetime, timedelta, timezone

    from app.services.reservations import release_expired

    client_token, admin_token, release = _peticion_en_tramit(client, db, "envio")
    peticion_id = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id

    item = Item(release_id=release.id, price=28, condition=CondicionItem.segona_ma, status=ItemStatus.disponible)
    db.add(item)
    db.commit()
    client.post(
        f"/admin/peticiones/{peticion_id}/vincular-item",
        json={"item_id": str(item.id)},
        headers=_auth(admin_token),
    )
    resp = client.post(f"/me/peticiones/{peticion_id}/comprar", headers=_auth(client_token))
    assert resp.status_code == 200

    db.expire_all()
    item_db = db.get(Item, item.id)
    assert item_db.reserved_for_peticion_id is None  # ja transferit al carret
    item_db.reserved_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    release_expired(db)

    db.expire_all()
    assert db.get(Item, item.id).status.value == "disponible"
    assert db.get(PeticionCliente, uuid.UUID(str(peticion_id))).status.value == "caducada"


def test_checkout_start_no_bloqueja_exemplar_de_peticio_ja_al_carret(db, client):
    """Regressió: /checkout/start cridava reserve_items() sobre TOT el
    carret, i aquesta només acceptava items amb status='disponible' — un
    exemplar ja transferit al carret via 'Comprar ara' (status='reservado',
    reserved_by_cart_id=aquest carret) queia sempre a 'failed', bloquejant
    per sempre el checkout de qualsevol petició Via 1."""
    client_token, admin_token, release = _peticion_en_tramit(client, db, "envio")
    peticion_id = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id

    item = Item(release_id=release.id, price=28, condition=CondicionItem.segona_ma, status=ItemStatus.disponible)
    db.add(item)
    db.commit()
    client.post(
        f"/admin/peticiones/{peticion_id}/vincular-item",
        json={"item_id": str(item.id)},
        headers=_auth(admin_token),
    )
    resp = client.post(f"/me/peticiones/{peticion_id}/comprar", headers=_auth(client_token))
    assert resp.status_code == 200

    resp_start = client.post("/checkout/start", headers=_auth(client_token))
    assert resp_start.status_code == 200
    assert resp_start.json()["reserved"] is True

    db.expire_all()
    item_db = db.get(Item, item.id)
    assert item_db.status.value == "reservado"
    assert item_db.reserved_by_cart_id is not None


def test_comprar_via1_falla_si_recollida_paga_botiga(db, client):
    client_token, admin_token, release = _peticion_en_tramit(client, db, "recollida_paga_botiga")
    peticion_id = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id

    item = Item(release_id=release.id, price=28, condition=CondicionItem.nou, status=ItemStatus.disponible)
    db.add(item)
    db.commit()
    client.post(
        f"/admin/peticiones/{peticion_id}/vincular-item",
        json={"item_id": str(item.id)},
        headers=_auth(admin_token),
    )

    resp = client.post(f"/me/peticiones/{peticion_id}/comprar", headers=_auth(client_token))
    assert resp.status_code == 409


def test_tpv_tanca_peticion_via2(db, client):
    client_token, admin_token, release = _peticion_en_tramit(client, db, "recollida_paga_botiga")
    peticion_id = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id

    item = Item(release_id=release.id, price=28, condition=CondicionItem.nou, quantity=1)
    db.add(item)
    db.commit()
    client.post(
        f"/admin/peticiones/{peticion_id}/vincular-item",
        json={"item_id": str(item.id)},
        headers=_auth(admin_token),
    )

    resp = client.post(
        "/admin/ventas-externas",
        json={
            "item_id": str(item.id), "channel": "mostrador", "payment_method": "efectivo",
            "sale_price": "28.00", "date": "2026-07-15T10:00:00",
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201

    db.expire_all()
    assert db.get(PeticionCliente, uuid.UUID(str(peticion_id))).status.value == "recollida"
    assert db.get(Item, item.id).quantity == 0
    assert db.get(Item, item.id).reserved_quantity == 0
    assert db.scalar(select(StockHold).where(StockHold.item_id == item.id)) is None


def test_reserves_recollida_llista_nomes_via2_reservades(db, client):
    # Via 2 (recollida_paga_botiga): ha d'aparèixer a la llista.
    client_token, admin_token, release = _peticion_en_tramit(client, db, "recollida_paga_botiga")
    peticion_id = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id
    item = Item(release_id=release.id, price=28, condition=CondicionItem.segona_ma, status=ItemStatus.disponible)
    db.add(item)
    db.commit()
    client.post(
        f"/admin/peticiones/{peticion_id}/vincular-item",
        json={"item_id": str(item.id)},
        headers=_auth(admin_token),
    )

    # Via 1 (envio): NO ha d'aparèixer, encara que també estigui 'reservada'.
    client_token2, admin_token2, release2 = _peticion_en_tramit(client, db, "envio")
    peticion_id2 = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release2.id)).id
    item2 = Item(release_id=release2.id, price=15, condition=CondicionItem.segona_ma, status=ItemStatus.disponible)
    db.add(item2)
    db.commit()
    client.post(
        f"/admin/peticiones/{peticion_id2}/vincular-item",
        json={"item_id": str(item2.id)},
        headers=_auth(admin_token),
    )

    resp = client.get("/admin/peticiones/reserves-recollida", headers=_auth(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["peticion_id"] == str(peticion_id)
    assert body[0]["item_id"] == str(item.id)
    assert body[0]["reserved_until"] is not None


def test_via2_reservada_apareix_a_orders_no_a_peticiones(db, client):
    client_token, admin_token, release = _peticion_en_tramit(client, db, "recollida_paga_botiga")
    peticion_id = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id

    item = Item(release_id=release.id, price=28, condition=CondicionItem.segona_ma, status=ItemStatus.disponible)
    db.add(item)
    db.commit()
    client.post(
        f"/admin/peticiones/{peticion_id}/vincular-item",
        json={"item_id": str(item.id)},
        headers=_auth(admin_token),
    )

    resp_peticiones = client.get("/me/peticiones", headers=_auth(client_token))
    assert resp_peticiones.status_code == 200
    assert all(p["id"] != str(peticion_id) for p in resp_peticiones.json())

    resp_orders = client.get("/me/orders", headers=_auth(client_token))
    assert resp_orders.status_code == 200
    body = resp_orders.json()
    assert len(body) == 1
    assert body[0]["id"] == str(peticion_id)
    assert body[0]["tipo"] == "reserva_botiga"
    assert body[0]["status"] == "reservada"
    assert body[0]["reserved_until"] is not None


def test_via2_recollida_apareix_a_orders_com_venda_botiga(db, client):
    client_token, admin_token, release = _peticion_en_tramit(client, db, "recollida_paga_botiga")
    peticion_id = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id

    item = Item(release_id=release.id, price=28, condition=CondicionItem.nou, status=ItemStatus.disponible)
    db.add(item)
    db.commit()
    client.post(
        f"/admin/peticiones/{peticion_id}/vincular-item",
        json={"item_id": str(item.id)},
        headers=_auth(admin_token),
    )
    client.post(
        "/admin/ventas-externas",
        json={
            "item_id": str(item.id), "channel": "mostrador", "payment_method": "efectivo",
            "sale_price": "28.00", "date": "2026-07-15T10:00:00",
        },
        headers=_auth(admin_token),
    )

    resp_peticiones = client.get("/me/peticiones", headers=_auth(client_token))
    assert all(p["id"] != str(peticion_id) for p in resp_peticiones.json())

    resp_orders = client.get("/me/orders", headers=_auth(client_token))
    body = resp_orders.json()
    assert len(body) == 1
    assert body[0]["tipo"] == "venda_botiga"
    assert body[0]["status"] == "recollida"


def test_aceptar_envio_crea_order_pendent_de_pagament(db, client):
    """Des d'aquesta funcionalitat, envio/recollida_paga_ara es paguen JA EN
    ACCEPTAR: una Order (pendent de pagament fins que Redsys l'autoritza)
    apareix de seguida a /me/orders, encara sense exemplar assignat."""
    client_token, admin_token, release = _peticion_en_tramit(client, db, "envio")
    peticion_id = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id
    peticion_db = db.get(PeticionCliente, uuid.UUID(str(peticion_id)))
    assert peticion_db.order_id is not None

    resp_orders = client.get("/me/orders", headers=_auth(client_token))
    body = resp_orders.json()
    assert len(body) == 1
    assert body[0]["id"] == str(peticion_db.order_id)
    assert body[0]["tipo"] == "comanda"
    assert body[0]["status"] == "pendiente_pago"


def test_vincular_item_sense_pagament_previ_cau_al_flux_antic(db, client):
    """Si l'Order creada en acceptar encara no s'ha pagat (Redsys no ha
    confirmat), vincular l'exemplar ha de caure al comportament antic:
    reservar-lo sense caducitat i esperar que el client faci "Comprar ara"."""
    client_token, admin_token, release = _peticion_en_tramit(client, db, "envio")
    peticion_id = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id

    item = Item(release_id=release.id, price=28, condition=CondicionItem.nou, quantity=1)
    db.add(item)
    db.commit()
    client.post(
        f"/admin/peticiones/{peticion_id}/vincular-item",
        json={"item_id": str(item.id)},
        headers=_auth(admin_token),
    )

    resp_peticiones = client.get("/me/peticiones", headers=_auth(client_token))
    assert any(p["id"] == str(peticion_id) for p in resp_peticiones.json())

    db.expire_all()
    assert db.get(PeticionCliente, uuid.UUID(str(peticion_id))).status.value == "reservada"
    assert db.get(Item, item.id).reserved_quantity == 1
    hold = db.scalar(select(StockHold).where(StockHold.item_id == item.id))
    assert hold is not None and hold.reserved_until is None


def test_aceptar_envio_sense_adreca_falla(db, client):
    client_token = _login(client, "client@example.com")
    admin_token = _admin_token(client, db)
    release = _seed_release(db)
    peticion = client.post(
        "/me/peticiones", json={"release_id": str(release.id)}, headers=_auth(client_token)
    ).json()
    client.patch(
        f"/admin/peticiones/{peticion['id']}/precio",
        json={"estimated_price": "28.00"},
        headers=_auth(admin_token),
    )

    resp = client.post(
        f"/me/peticiones/{peticion['id']}/aceptar",
        json={"metodo_entrega": "envio"},
        headers=_auth(client_token),
    )
    assert resp.status_code == 422


def test_aceptar_envio_amb_adreca_predeterminada(db, client):
    from app.models import Address

    client_token = _login(client, "client@example.com")
    admin_token = _admin_token(client, db)
    release = _seed_release(db)
    user = db.scalar(select(User).where(User.email == "client@example.com"))
    db.add(Address(
        user_id=user.id, recipient_name="Client Test", address_line1="Carrer Fals 1",
        postal_code="08001", city="Barcelona", country="ES", is_default=True,
    ))
    db.commit()

    peticion = client.post(
        "/me/peticiones", json={"release_id": str(release.id)}, headers=_auth(client_token)
    ).json()
    client.patch(
        f"/admin/peticiones/{peticion['id']}/precio",
        json={"estimated_price": "28.00"},
        headers=_auth(admin_token),
    )
    resp = client.post(
        f"/me/peticiones/{peticion['id']}/aceptar",
        json={"metodo_entrega": "envio"},
        headers=_auth(client_token),
    )
    assert resp.status_code == 200
    assert resp.json()["order_id"] is not None


def test_admin_marca_pagada_manualment_i_completa_flux(db, client):
    """Sense pasarel·la Redsys configurada (falten credencials reals),
    l'admin ha de poder marcar la comanda com a pagada a mà des de Vendes
    Web (com ja fa amb qualsevol comanda 'paga a botiga'), i que la resta
    del flux (arribada -> assignació automàtica) funcioni igual."""
    client_token, admin_token, release = _peticion_en_tramit(client, db, "envio")
    peticion_id = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id
    peticion_db = db.get(PeticionCliente, uuid.UUID(str(peticion_id)))

    resp = client.patch(
        f"/admin/orders/{peticion_db.order_id}/status",
        json={"status": "pagado"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "pagado"

    item = Item(release_id=release.id, price=28, condition=CondicionItem.segona_ma, status=ItemStatus.disponible)
    db.add(item)
    db.commit()
    resp = client.post(
        f"/admin/peticiones/{peticion_id}/vincular-item",
        json={"item_id": str(item.id)},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "recollida"

    db.expire_all()
    assert db.get(Item, item.id).status.value == "vendido"


def test_vincular_item_amb_order_ja_pagada_completa_directament(db, client):
    """Un cop Redsys confirma el pagament (simulem marcant l'Order 'pagado'
    directament), vincular l'exemplar l'ha d'assignar de seguida: la
    petició passa a 'recollida' sense passar per 'reservada'."""
    from app.models import Order, OrderItem, OrderStatus

    client_token, admin_token, release = _peticion_en_tramit(client, db, "envio")
    peticion_id = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id
    peticion_db = db.get(PeticionCliente, uuid.UUID(str(peticion_id)))
    order = db.get(Order, peticion_db.order_id)
    order.status = OrderStatus.pagado
    db.commit()

    item = Item(release_id=release.id, price=28, condition=CondicionItem.segona_ma, status=ItemStatus.disponible)
    db.add(item)
    db.commit()

    resp = client.post(
        f"/admin/peticiones/{peticion_id}/vincular-item",
        json={"item_id": str(item.id)},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "recollida"

    db.expire_all()
    item_db = db.get(Item, item.id)
    assert item_db.status.value == "vendido"

    linia = db.scalar(select(OrderItem).where(OrderItem.order_id == order.id))
    assert linia.item_id == item.id
    assert linia.release_id is None


def test_reintentar_pagament_denegat_crea_nova_order(db, client):
    from app.models import Order, OrderStatus

    client_token, admin_token, release = _peticion_en_tramit(client, db, "envio")
    peticion_id = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id
    peticion_db = db.get(PeticionCliente, uuid.UUID(str(peticion_id)))
    order_original_id = peticion_db.order_id
    order = db.get(Order, order_original_id)
    order.status = OrderStatus.cancelado
    db.commit()

    resp = client.post(f"/me/peticiones/{peticion_id}/reintentar-pagament", headers=_auth(client_token))
    assert resp.status_code == 200
    nou_order_id = resp.json()["order_id"]
    assert nou_order_id != str(order_original_id)

    db.expire_all()
    assert str(db.get(PeticionCliente, uuid.UUID(str(peticion_id))).order_id) == nou_order_id

    resp_peticiones = client.get("/me/peticiones", headers=_auth(client_token))
    peticio_out = next(p for p in resp_peticiones.json() if p["id"] == str(peticion_id))
    assert peticio_out["pagament_pendent"] is True


def test_crear_peticion_tienda_i_saltar_acceptacio(db, client):
    """L'admin crea una petició de tienda per un client que ja té compte
    (trucada o mostrador): en fixar preu, s'ha de saltar 'pendent_acceptacio'
    i anar directament a 'acceptada' amb recollida i pagament a botiga."""
    admin_token = _admin_token(client, db)
    _login(client, "mostrador@example.com")
    cliente = db.scalar(select(User).where(User.email == "mostrador@example.com"))
    release = _seed_release(db, artista="Grup Tienda", titulo="Disc Tienda")

    resp = client.post(
        "/admin/peticiones/tienda",
        json={"user_id": str(cliente.id), "release_id": str(release.id), "client_notes": "Ha trucat per telèfon"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["channel"] == "tienda"
    assert body["status"] == "pendent"
    assert body["user_email"] == "mostrador@example.com"

    resp = client.patch(
        f"/admin/peticiones/{body['id']}/precio",
        json={"estimated_price": "22.50"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    body2 = resp.json()
    assert body2["status"] == "acceptada"
    assert body2["chosen_delivery_method"] == "recollida_paga_botiga"

    # Continua igual que qualsevol altra petició acceptada: es pot vincular a solicitud.
    resp = client.post(
        f"/admin/peticiones/{body['id']}/vincular-solicitud",
        json={"cantidad": 1},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201


def test_crear_peticion_tienda_text_lliure(db, client):
    admin_token = _admin_token(client, db)
    _login(client, "mostrador2@example.com")
    cliente = db.scalar(select(User).where(User.email == "mostrador2@example.com"))

    resp = client.post(
        "/admin/peticiones/tienda",
        json={"user_id": str(cliente.id), "free_artist": "Grup Rar", "free_title": "Disc Rar"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    assert resp.json()["release_id"] is None
    assert resp.json()["artista"] == "Grup Rar"


def test_crear_peticion_tienda_sense_disc_ni_text_falla(db, client):
    admin_token = _admin_token(client, db)
    _login(client, "mostrador3@example.com")
    cliente = db.scalar(select(User).where(User.email == "mostrador3@example.com"))

    resp = client.post(
        "/admin/peticiones/tienda", json={"user_id": str(cliente.id)}, headers=_auth(admin_token),
    )
    assert resp.status_code == 422


def test_crear_peticion_tienda_usuari_inexistent_falla(db, client):
    admin_token = _admin_token(client, db)
    release = _seed_release(db)

    resp = client.post(
        "/admin/peticiones/tienda",
        json={"user_id": str(uuid.uuid4()), "release_id": str(release.id)},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


def test_release_expired_allibera_i_caduca_peticio(db, client):
    from datetime import datetime, timedelta, timezone

    from app.services.reservations import release_expired

    client_token, admin_token, release = _peticion_en_tramit(client, db, "recollida_paga_botiga")
    peticion_id = db.scalar(select(PeticionCliente).where(PeticionCliente.release_id == release.id)).id

    item = Item(release_id=release.id, price=28, condition=CondicionItem.nou, quantity=1)
    db.add(item)
    db.commit()
    client.post(
        f"/admin/peticiones/{peticion_id}/vincular-item",
        json={"item_id": str(item.id)},
        headers=_auth(admin_token),
    )

    # Simulem que ja han passat les 72h (StockHold, no Item.reserved_until).
    hold = db.scalar(select(StockHold).where(StockHold.item_id == item.id))
    hold.reserved_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    release_expired(db)

    db.expire_all()
    assert db.get(Item, item.id).reserved_quantity == 0
    assert db.get(StockHold, hold.id) is None
    assert db.get(PeticionCliente, uuid.UUID(str(peticion_id))).status.value == "caducada"
