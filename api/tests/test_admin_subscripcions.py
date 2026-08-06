"""Test d'integració del cicle d'admin del club del disc: la tria de
catàleg (la safata), proposar assignacions per als cobraments pendents,
revisar-les i confirmar un enviament sencer. Verifica que la confirmació
genera una única venda normal amb tantes línies com discos, visible a
`/admin/orders?origen=subscripcio` igual que qualsevol altra comanda web."""

import contextlib
import io
import re
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    Address, CobramentSubscripcio, ConfiguracioSubscripcio, EstatCobrament, EstatSubscripcio,
    Item, ItemStatus, Release, Subscripcio, User,
)


def _login(client, email):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _admin_token(client, db, email="admin@example.com") -> str:
    _login(client, email)
    user = db.scalar(select(User).where(User.email == email))
    user.rol = "admin"
    db.commit()
    return _login(client, email)


def _config(db) -> ConfiguracioSubscripcio:
    c = ConfiguracioSubscripcio(
        id=1, preu_per_disc=Decimal("25.00"), periodicitats_mesos_disponibles=[1], quantitats_disponibles=[1, 2, 3],
    )
    db.add(c)
    db.commit()
    return c


def _seed(db, *, quantitat=1, email="fan@example.com"):
    user = User(email=email, nombre="Fan")
    db.add(user)
    db.flush()
    address = Address(user_id=user.id, nombre_destinatario="Fan", linea1="C. Falsa 1", ciudad="BCN", cp="08001")
    db.add(address)
    db.flush()
    preu_periode = Decimal("25.00") * quantitat
    subscripcio = Subscripcio(
        user_id=user.id, address_id=address.id,
        periodicitat_mesos=1, quantitat=quantitat, preu_periode=preu_periode,
        estat=EstatSubscripcio.activa, redsys_identifier="TOKEN-123",
        proxima_facturacio=date.today(),
    )
    db.add(subscripcio)
    db.flush()
    cobrament = CobramentSubscripcio(
        subscripcio_id=subscripcio.id, periode=date.today(), import_=preu_periode,
        estat=EstatCobrament.cobrat, ds_order="123abcdef01",
    )
    db.add(cobrament)
    db.commit()
    return subscripcio, cobrament


def _item(db, precio="22.00", pool=True, titulo="Àlbum") -> Item:
    release = Release(artista="Artista", titulo=titulo, formato="LP")
    db.add(release)
    db.flush()
    item = Item(release_id=release.id, precio=Decimal(precio), status=ItemStatus.disponible, subscripcio_pool=pool)
    db.add(item)
    db.commit()
    return item


def test_cicle_complet_proposar_revisar_confirmar(db, client):
    admin_access = _admin_token(client, db)
    headers = {"Authorization": f"Bearer {admin_access}"}
    _config(db)
    subscripcio, cobrament = _seed(db)
    item = _item(db)

    pendents = client.get("/admin/subscripcions/cobraments-pendents", headers=headers)
    assert pendents.status_code == 200
    assert len(pendents.json()) == 1

    proposar = client.post("/admin/subscripcions/proposar", headers=headers)
    assert proposar.status_code == 200
    assert proposar.json()["enviaments_proposats"] == 1
    assert proposar.json()["errors"] == []

    revisio = client.get("/admin/subscripcions/assignacions", headers=headers)
    assert revisio.status_code == 200
    enviaments = revisio.json()
    assert len(enviaments) == 1
    enviament = enviaments[0]
    assert enviament["cobrament_id"] == str(cobrament.id)
    assert len(enviament["discos"]) == 1
    disc = enviament["discos"][0]
    assert disc["item"]["id"] == str(item.id)
    assert disc["item"]["marge_pct"] == round(22.00 / 25.00 * 100, 1)

    db.expire_all()
    assert db.get(Item, item.id).status == ItemStatus.reservado

    confirmar = client.post(f"/admin/subscripcions/cobraments/{cobrament.id}/confirmar", headers=headers)
    assert confirmar.status_code == 200
    order_id = confirmar.json()["order_id"]

    orders = client.get("/admin/orders?origen=subscripcio", headers=headers)
    assert orders.status_code == 200
    assert len(orders.json()) == 1
    assert orders.json()[0]["id"] == order_id
    assert orders.json()[0]["status"] == "pagado"

    db.expire_all()
    assert db.get(Item, item.id).status == ItemStatus.vendido

    pendents_despres = client.get("/admin/subscripcions/cobraments-pendents", headers=headers)
    assert pendents_despres.json() == []

    llista = client.get("/admin/subscripcions", headers=headers)
    assert llista.status_code == 200
    assert llista.json()[0]["ultim_disc_rebut"] == "Artista — Àlbum"


def test_detall_de_subscriptor_inclou_generes_i_historic_complet(db, client):
    from app.models import Assignacio, EstatAssignacio, Release

    admin_access = _admin_token(client, db)
    headers = {"Authorization": f"Bearer {admin_access}"}
    _config(db)
    subscripcio, cobrament = _seed(db)
    subscripcio.generes_preferits = ["Jazz"]

    release = Release(artista="Artista", titulo="Àlbum", formato="LP", genero="Jazz")
    db.add(release)
    db.flush()
    db.add(Assignacio(
        cobrament_id=cobrament.id, subscripcio_id=subscripcio.id, release_id=release.id,
        estat=EstatAssignacio.confirmada,
    ))
    db.commit()

    detall = client.get(f"/admin/subscripcions/{subscripcio.id}", headers=headers)
    assert detall.status_code == 200
    body = detall.json()
    assert body["email"] == "fan@example.com"
    assert body["generes_preferits"] == ["Jazz"]
    assert len(body["discos_rebuts"]) == 1
    assert body["discos_rebuts"][0]["titulo"] == "Àlbum"
    assert body["adreca"]["ciudad"] == "BCN"

    # les rutes d'un sol segment registrades abans de "/{subscripcio_id}"
    # han de continuar funcionant (no interceptades pel path param)
    assert client.get("/admin/subscripcions/cobraments-pendents", headers=headers).status_code == 200
    assert client.get("/admin/subscripcions/assignacions", headers=headers).status_code == 200
    assert client.get("/admin/subscripcions/configuracio", headers=headers).status_code == 200
    assert client.get("/admin/subscripcions/catalog", headers=headers).status_code == 200


def test_confirmar_enviament_amb_quantitat_2_genera_una_sola_comanda_amb_2_linies(db, client):
    admin_access = _admin_token(client, db)
    headers = {"Authorization": f"Bearer {admin_access}"}
    _config(db)
    subscripcio, cobrament = _seed(db, quantitat=2)
    item1 = _item(db, precio="20.00", titulo="Disc A")
    item2 = _item(db, precio="30.00", titulo="Disc B")

    client.post("/admin/subscripcions/proposar", headers=headers)

    revisio = client.get("/admin/subscripcions/assignacions", headers=headers).json()
    assert len(revisio) == 1
    assert len(revisio[0]["discos"]) == 2

    confirmar = client.post(f"/admin/subscripcions/cobraments/{cobrament.id}/confirmar", headers=headers)
    assert confirmar.status_code == 200
    order_id = confirmar.json()["order_id"]

    detall = client.get(f"/admin/orders/{order_id}", headers=headers)
    assert detall.status_code == 200
    body = detall.json()
    assert body["total"] == "50.00"
    assert len(body["items"]) == 2
    suma_linies = sum(Decimal(i["precio"]) for i in body["items"])
    assert suma_linies == Decimal("50.00")

    db.expire_all()
    assert db.get(Item, item1.id).status == ItemStatus.vendido
    assert db.get(Item, item2.id).status == ItemStatus.vendido


def test_sense_match_no_desapareix_i_es_pot_reintentar(db, client):
    """Regressió: amb la safata buida, "Generar proposta" creava un
    enviament sense_match que no sortia enlloc (ni a "cobraments pendents",
    perquè ja tenia Assignacio; ni a "assignacions", que per defecte només
    mostrava proposada) — quedava encallat sense manera de recuperar-lo."""
    admin_access = _admin_token(client, db)
    headers = {"Authorization": f"Bearer {admin_access}"}
    _config(db)
    subscripcio, cobrament = _seed(db)
    # safata buida a propòsit

    proposar = client.post("/admin/subscripcions/proposar", headers=headers)
    assert proposar.status_code == 200
    assert proposar.json() == {"enviaments_proposats": 1, "errors": []}

    # ja no queda a "pendents" (té Assignacio), però ha de seguir visible
    assert client.get("/admin/subscripcions/cobraments-pendents", headers=headers).json() == []
    revisio = client.get("/admin/subscripcions/assignacions", headers=headers).json()
    assert len(revisio) == 1
    assert revisio[0]["discos"][0]["estat"] == "sense_match"
    assert revisio[0]["discos"][0]["item"] is None

    # confirmar encara no és possible (cap disc trobat)
    confirmar_massa_aviat = client.post(f"/admin/subscripcions/cobraments/{cobrament.id}/confirmar", headers=headers)
    assert confirmar_massa_aviat.status_code == 409

    # l'admin afegeix un disc a la safata i reintenta, sense esperar cap cobrament nou
    item = _item(db)
    reintentar = client.post(f"/admin/subscripcions/cobraments/{cobrament.id}/reintentar", headers=headers)
    assert reintentar.status_code == 200
    assert reintentar.json()["trobats"] == 1
    assert reintentar.json()["enviament"]["discos"][0]["item"]["id"] == str(item.id)

    confirmar = client.post(f"/admin/subscripcions/cobraments/{cobrament.id}/confirmar", headers=headers)
    assert confirmar.status_code == 200

    # un cop confirmat, ja no ha de sortir mai més a "per gestionar"
    assert client.get("/admin/subscripcions/assignacions", headers=headers).json() == []


def test_confirmar_parcial_tanca_els_sense_match_restants_com_omesa(db, client):
    """Si la safata només té prou discos per a una part de la quantitat
    pagada, confirmar l'enviament no ha de deixar un sense_match zombi que
    reaparegui per sempre a la pantalla de gestió."""
    admin_access = _admin_token(client, db)
    headers = {"Authorization": f"Bearer {admin_access}"}
    _config(db)
    subscripcio, cobrament = _seed(db, quantitat=2)
    _item(db, precio="20.00")  # només 1 disc per a quantitat=2

    client.post("/admin/subscripcions/proposar", headers=headers)
    revisio = client.get("/admin/subscripcions/assignacions", headers=headers).json()
    estats = sorted(d["estat"] for d in revisio[0]["discos"])
    assert estats == ["proposada", "sense_match"]

    confirmar = client.post(f"/admin/subscripcions/cobraments/{cobrament.id}/confirmar", headers=headers)
    assert confirmar.status_code == 200

    assert client.get("/admin/subscripcions/assignacions", headers=headers).json() == []


def test_catalog_picker_filtra_i_permet_afegir_treure_del_pool(db, client):
    admin_access = _admin_token(client, db)
    headers = {"Authorization": f"Bearer {admin_access}"}
    _config(db)
    fora_pool = _item(db, precio="22.00", pool=False, titulo="Encara no elegible")

    llista = client.get("/admin/subscripcions/catalog", headers=headers)
    assert llista.status_code == 200
    ids = {row["item_id"] for row in llista.json()}
    assert str(fora_pool.id) in ids
    assert next(r for r in llista.json() if r["item_id"] == str(fora_pool.id))["subscripcio_pool"] is False

    nomes_pool = client.get("/admin/subscripcions/catalog?nomes_pool=true", headers=headers)
    assert nomes_pool.json() == []

    patch = client.patch(
        f"/admin/subscripcions/catalog/{fora_pool.id}", json={"subscripcio_pool": True}, headers=headers,
    )
    assert patch.status_code == 200
    assert patch.json()["subscripcio_pool"] is True

    nomes_pool_despres = client.get("/admin/subscripcions/catalog?nomes_pool=true", headers=headers)
    assert len(nomes_pool_despres.json()) == 1


def test_seleccio_automatica_afegeix_al_pool_respectant_limit_i_filtres(db, client):
    admin_access = _admin_token(client, db)
    headers = {"Authorization": f"Bearer {admin_access}"}
    _config(db)  # preu_per_disc=25.00
    dins_marge = [_item(db, precio="24.00", titulo=f"Dins {i}", pool=False) for i in range(3)]
    fora_marge = _item(db, precio="90.00", titulo="Massa car", pool=False)
    ja_al_pool = _item(db, precio="24.00", titulo="Ja hi era", pool=True)

    r = client.post(
        "/admin/subscripcions/catalog/seleccio-automatica",
        json={"marge_min_pct": 70, "marge_max_pct": 120, "limit": 2},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["afegits"] == 2  # limitat a 2, encara que 3 discos compleixen el marge

    db.expire_all()
    en_pool = {i.id for i in dins_marge if db.get(Item, i.id).subscripcio_pool}
    assert len(en_pool) == 2
    assert db.get(Item, fora_marge.id).subscripcio_pool is False  # fora del marge, mai tocat
    assert db.get(Item, ja_al_pool.id).subscripcio_pool is True  # ja hi era, no compta pel límit


def test_informe_mensual_agrega_nomes_les_dades_del_mes_demanat(db, client):
    """Dades sintètiques repartides entre gener i febrer del 2026, per
    verificar que l'informe d'un mes no arrossega res de l'altre."""
    from app.models import Assignacio, EstatAssignacio

    admin_access = _admin_token(client, db)
    headers = {"Authorization": f"Bearer {admin_access}"}
    _config(db)

    # Subscripció A: alta (primer cobrament) i disc enviat al gener.
    sub_a, cobrament_a = _seed(db, email="gener@example.com")
    cobrament_a.periode = date(2026, 1, 5)
    cobrament_a.estat = EstatCobrament.cobrat
    cobrament_a.ds_order = "genabcdef01"
    release_a = Release(artista="A", titulo="Disc A", formato="LP")
    db.add(release_a)
    db.flush()
    db.add(Assignacio(
        cobrament_id=cobrament_a.id, subscripcio_id=sub_a.id, release_id=release_a.id,
        estat=EstatAssignacio.confirmada, confirmada_at=datetime(2026, 1, 8, tzinfo=timezone.utc),
    ))

    # Subscripció B: alta al gener, però amb una renovació fallida al febrer
    # (targeta caducada) — ha de comptar com a "noves" al gener i com a
    # "fallit" al febrer, no als dos mesos alhora.
    sub_b, cobrament_b1 = _seed(db, email="febrer@example.com")
    cobrament_b1.periode = date(2026, 1, 10)
    cobrament_b1.estat = EstatCobrament.cobrat
    cobrament_b1.ds_order = "febabcdef01"
    cobrament_b2 = CobramentSubscripcio(
        subscripcio_id=sub_b.id, periode=date(2026, 2, 2), import_=sub_b.preu_periode,
        estat=EstatCobrament.fallit, ds_order="febfallit01",
    )
    db.add(cobrament_b2)

    # Subscripció C: es dona de baixa al febrer.
    sub_c, cobrament_c = _seed(db, email="baixa@example.com")
    cobrament_c.periode = date(2026, 1, 15)
    cobrament_c.estat = EstatCobrament.cobrat
    cobrament_c.ds_order = "baixaabcde1"
    sub_c.estat = EstatSubscripcio.cancel_lada
    sub_c.cancel_lada_at = datetime(2026, 2, 20, tzinfo=timezone.utc)

    db.commit()

    informe_gener = client.get("/admin/subscripcions/informe/2026/1", headers=headers)
    assert informe_gener.status_code == 200
    body_gener = informe_gener.json()
    assert body_gener["any"] == 2026
    assert body_gener["mes"] == 1
    assert body_gener["noves_subscripcions"] == 3  # A, B, C: primer cobrament de cadascuna cau al gener
    assert body_gener["cobraments_ok"] == 3
    assert Decimal(body_gener["import_total"]) == Decimal("75.00")  # 3 x 25.00
    assert body_gener["cobraments_fallits"] == 0
    assert body_gener["discos_enviats"] == 1
    assert body_gener["baixes"] == 0

    informe_febrer = client.get("/admin/subscripcions/informe/2026/2", headers=headers)
    assert informe_febrer.status_code == 200
    body_febrer = informe_febrer.json()
    assert body_febrer["noves_subscripcions"] == 0
    assert body_febrer["cobraments_ok"] == 0
    assert body_febrer["cobraments_fallits"] == 1
    assert body_febrer["discos_enviats"] == 0
    assert body_febrer["baixes"] == 1
    # subscriptors_actius no depèn del mes demanat, és l'estat actual (A i B, C ja cancel·lada)
    assert body_febrer["subscriptors_actius"] == 2
    assert body_gener["subscriptors_actius"] == 2

    invalid = client.get("/admin/subscripcions/informe/2026/13", headers=headers)
    assert invalid.status_code == 422


def test_configuracio_es_pot_llegir_i_actualitzar(db, client):
    admin_access = _admin_token(client, db)
    headers = {"Authorization": f"Bearer {admin_access}"}

    inicial = client.get("/admin/subscripcions/configuracio", headers=headers)
    assert inicial.status_code == 200

    update = client.patch(
        "/admin/subscripcions/configuracio",
        json={"preu_per_disc": 22.50, "periodicitats_mesos_disponibles": [1, 2], "quantitats_disponibles": [1, 2, 3]},
        headers=headers,
    )
    assert update.status_code == 200
    body = update.json()
    assert body["preu_per_disc"] == "22.50"
    assert body["periodicitats_mesos_disponibles"] == [1, 2]
    assert body["quantitats_disponibles"] == [1, 2, 3]
