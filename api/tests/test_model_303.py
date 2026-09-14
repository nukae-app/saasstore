"""Tests del informe de caselles del Model 303 (Fase 5) — en particular que
el desglossament corrent (28/29) vs béns d'inversió (30/31) surt correcte
gràcies al fet que un FixedAsset mai passa per Despesa. També RECC,
prorrata especial, importació diferida i compensació entre trimestres
(ver docs/PLAN_MODELO303_FITXER.md)."""

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    CategoriaDespesa, CondicionItem, ConfiguracioBotiga, Despesa, DestinoIva, EstatPagamentDespesa,
    IvaCompensacioPendent, Item, Order, OrderItem, OrderStatus, Release, TipusIva, User,
)


def _admin_token(client, db) -> str:
    import contextlib
    import io
    import re

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": "admin@example.com"}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    user = db.scalar(select(User).where(User.email == "admin@example.com"))
    user.role = "admin"
    db.commit()
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_model_303_desglossa_corrent_vs_inversio(client, db):
    token = _admin_token(client, db)
    db.add(TipusIva(name="General", percentage=Decimal("21.00"), default_new=True, active=True))
    db.commit()

    # Venda: 100.00 total, 21% -> base 82.64, cuota 17.36 (repercutit).
    release = Release(artista="A", title="T", formato="LP")
    db.add(release)
    db.commit()
    item = Item(release_id=release.id, price=Decimal("100.00"), acquisition_cost=Decimal("40.00"), condition=CondicionItem.nou, quantity=1)
    db.add(item)
    db.commit()
    resp = client.post(
        "/admin/ventas-externas",
        json={
            "item_id": str(item.id), "channel": "mostrador", "payment_method": "efectivo",
            "sale_price": "100.00", "quantity": 1, "date": "2026-04-15T10:00:00",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    cuota_repercutida = Decimal(str(resp.json()["vat_amount"]))

    # Despesa corrent: base 50.00, cuota 10.50.
    resp_despesa = client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-04-20", "supplier_name": "Proveïdor", "category": "subministraments",
            "concept": "Llum", "taxable_base": "50.00", "vat_pct": "21.00",
        },
        headers=_auth(token),
    )
    assert resp_despesa.status_code == 201

    # Actiu (béns d'inversió): cost 1000.00, IVA 210.00.
    resp_actiu = client.post(
        "/admin/actius",
        json={
            "name": "Ordinador", "category": "equips_informatics", "acquisition_date": "2026-04-25",
            "acquisition_cost": "1000.00", "vat_amount": "210.00", "annual_depreciation_pct": "25.00",
        },
        headers=_auth(token),
    )
    assert resp_actiu.status_code == 201

    resp = client.get("/admin/aeat/303/2026/2", headers=_auth(token))  # T2 = abr-may-jun
    assert resp.status_code == 200
    body = resp.json()

    assert Decimal(body["repercutit_general"]["cuota"]) == cuota_repercutida
    assert Decimal(body["casella_27_cuota_meritada"]) == cuota_repercutida

    assert body["casella_28_base_corrent"] == "50.00"
    assert body["casella_29_cuota_corrent"] == "10.50"
    assert body["casella_30_base_inversio"] == "1000.00"
    assert body["casella_31_cuota_inversio"] == "210.00"

    total_a_deduir = Decimal("10.50") + Decimal("210.00")
    assert Decimal(body["casella_45_total_a_deduir"]) == total_a_deduir
    assert Decimal(body["casella_46_resultat_regim_general"]) == cuota_repercutida - total_a_deduir
    assert Decimal(body["casella_64_resultat_liquidacio"]) == cuota_repercutida - total_a_deduir
    assert body["nota_rebu"] is False


def test_model_303_trimestre_invalid_dona_422(client, db):
    token = _admin_token(client, db)
    resp = client.get("/admin/aeat/303/2026/5", headers=_auth(token))
    assert resp.status_code == 422


def test_model_303_recc_usa_data_de_cobrament_no_de_facturacio(client, db):
    """Emesa/creada al T1 però cobrada al T2: sota RECC, compta al T2."""
    token = _admin_token(client, db)
    config = db.scalar(select(ConfiguracioBotiga))
    config.recc_actiu = True
    db.commit()

    order = Order(
        status=OrderStatus.pagado, contact_email="client@example.com", total=Decimal("121.00"),
        shipping_method="envio", created_at=datetime(2026, 2, 10, tzinfo=timezone.utc),
        paid_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
    )
    db.add(order)
    db.commit()
    db.add(OrderItem(order_id=order.id, price=Decimal("121.00"), quantity=1, vat_pct=Decimal("21.00")))
    db.commit()

    t1 = client.get("/admin/aeat/303/2026/1", headers=_auth(token)).json()
    t2 = client.get("/admin/aeat/303/2026/2", headers=_auth(token)).json()
    assert Decimal(t1["casella_27_cuota_meritada"]) == Decimal("0.00")
    assert Decimal(t2["casella_27_cuota_meritada"]) == Decimal("21.00")
    # Informatiu RECC: coincideix amb el que ja s'ha comptat a 27.
    assert Decimal(t2["casella_63_cuota_recc"]) == Decimal("21.00")


def _seed_despesa(db, total: str, base: str, vat: str, destino: DestinoIva = DestinoIva.activitat_gravada, importacio: bool = False) -> Despesa:
    d = Despesa(
        invoice_date=date(2026, 4, 10), supplier_name="Prov", category=CategoriaDespesa.subministraments,
        concept="Test", taxable_base=Decimal(base), vat_pct=Decimal("21.00"), vat_amount=Decimal(vat),
        total=Decimal(total), destino_iva=destino, importacio_diferida=importacio,
        payment_status=EstatPagamentDespesa.pagat, payment_date=date(2026, 4, 10),
    )
    db.add(d)
    db.commit()
    return d


def test_model_303_prorrata_especial_redueix_deduccio_de_despeses_comunes(client, db):
    token = _admin_token(client, db)
    config = db.scalar(select(ConfiguracioBotiga))
    config.prorrata_pct_provisional = Decimal("50.00")
    db.commit()

    _seed_despesa(db, "121.00", "100.00", "21.00", destino=DestinoIva.activitat_gravada)  # dedueix 100%
    _seed_despesa(db, "121.00", "100.00", "21.00", destino=DestinoIva.activitat_exempta)  # dedueix 0%
    _seed_despesa(db, "121.00", "100.00", "21.00", destino=DestinoIva.comu)  # dedueix 50%

    body = client.get("/admin/aeat/303/2026/2", headers=_auth(token)).json()
    # 21.00 (gravada 100%) + 0.00 (exempta) + 10.50 (comú al 50%) = 31.50
    assert Decimal(body["casella_29_cuota_corrent"]) == Decimal("31.50")
    assert Decimal(body["casella_28_base_corrent"]) == Decimal("300.00")  # la base es reporta sencera


def test_model_303_importacio_diferida_va_a_casella_77_no_28_29(client, db):
    token = _admin_token(client, db)
    _seed_despesa(db, "121.00", "100.00", "21.00", importacio=True)
    _seed_despesa(db, "121.00", "100.00", "21.00", importacio=False)

    body = client.get("/admin/aeat/303/2026/2", headers=_auth(token)).json()
    assert Decimal(body["casella_28_base_corrent"]) == Decimal("100.00")  # només la no diferida
    assert Decimal(body["casella_29_cuota_corrent"]) == Decimal("21.00")
    assert Decimal(body["casella_77_iva_importacio_diferit"]) == Decimal("21.00")


def test_generar_fitxer_303_requereix_nif(client, db):
    token = _admin_token(client, db)
    resp = client.post(
        "/admin/aeat/303/2026/2/fitxer", json={"tipo_declaracion": "N"}, headers=_auth(token),
    )
    assert resp.status_code == 422


def test_generar_fitxer_303_ok_i_desa_compensacio_pendent(client, db):
    token = _admin_token(client, db)
    config = db.scalar(select(ConfiguracioBotiga))
    config.nif = "B12345678"
    db.commit()

    resp = client.post(
        "/admin/aeat/303/2026/2/fitxer", json={"tipo_declaracion": "N"}, headers=_auth(token),
    )
    assert resp.status_code == 200
    contingut = resp.content.decode("iso-8859-1")
    assert contingut.startswith("<T303020262T0000>")
    assert contingut.endswith("</T303020262T0000>")
    assert "<T303" + "01000" + ">" in contingut
    assert "<T303" + "03000" + ">" in contingut

    pendent = db.scalar(
        select(IvaCompensacioPendent).where(
            IvaCompensacioPendent.fiscal_year == 2026, IvaCompensacioPendent.trimestre == 2,
        )
    )
    assert pendent is not None
    assert pendent.import_pendent == Decimal("0.00")  # sense IVA de cap tipus, resultat 0


def test_generar_fitxer_303_compensacio_superior_a_pendent_falla(client, db):
    token = _admin_token(client, db)
    config = db.scalar(select(ConfiguracioBotiga))
    config.nif = "B12345678"
    db.commit()

    resp = client.post(
        "/admin/aeat/303/2026/2/fitxer",
        json={"tipo_declaracion": "I", "import_compensacio_aplicada": "50.00"},
        headers=_auth(token),
    )
    assert resp.status_code == 422


def test_generar_fitxer_303_amb_prorrata_sense_cnae_falla(client, db):
    token = _admin_token(client, db)
    config = db.scalar(select(ConfiguracioBotiga))
    config.nif = "B12345678"
    config.prorrata_pct_provisional = Decimal("50.00")
    db.commit()

    resp = client.post(
        "/admin/aeat/303/2026/2/fitxer", json={"tipo_declaracion": "N"}, headers=_auth(token),
    )
    assert resp.status_code == 422


def test_generar_fitxer_303_amb_prorrata_i_cnae_inclou_pagina_5(client, db):
    token = _admin_token(client, db)
    config = db.scalar(select(ConfiguracioBotiga))
    config.nif = "B12345678"
    config.prorrata_pct_provisional = Decimal("50.00")
    db.commit()

    resp = client.post(
        "/admin/aeat/303/2026/2/fitxer",
        json={"tipo_declaracion": "N", "cnae_code": "476"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    contingut = resp.content.decode("iso-8859-1")
    assert "<T303" + "05000" + ">" in contingut


def test_generar_fitxer_303_seguent_trimestre_llegeix_compensacio_pendent(client, db):
    token = _admin_token(client, db)
    config = db.scalar(select(ConfiguracioBotiga))
    config.nif = "B12345678"
    db.commit()

    db.add(IvaCompensacioPendent(fiscal_year=2026, trimestre=1, import_pendent=Decimal("42.00")))
    db.commit()

    body = client.get("/admin/aeat/303/2026/2", headers=_auth(token)).json()
    assert Decimal(body["casella_110_compensacio_pendent_anterior"]) == Decimal("42.00")

    resp = client.post(
        "/admin/aeat/303/2026/2/fitxer",
        json={"tipo_declaracion": "I", "import_compensacio_aplicada": "10.00"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    pendent = db.scalar(
        select(IvaCompensacioPendent).where(
            IvaCompensacioPendent.fiscal_year == 2026, IvaCompensacioPendent.trimestre == 2,
        )
    )
    assert pendent.import_pendent == Decimal("32.00")  # 42.00 - 10.00 aplicats


def test_generar_fitxer_303_q1_llegeix_compensacio_del_4t_anterior(client, db):
    token = _admin_token(client, db)
    config = db.scalar(select(ConfiguracioBotiga))
    config.nif = "B12345678"
    db.commit()

    db.add(IvaCompensacioPendent(fiscal_year=2025, trimestre=4, import_pendent=Decimal("15.00")))
    db.commit()

    body = client.get("/admin/aeat/303/2026/1", headers=_auth(token)).json()
    assert Decimal(body["casella_110_compensacio_pendent_anterior"]) == Decimal("15.00")


def test_recc_i_prorrata_son_configurables_via_api(client, db):
    """Regressió: si aquests camps no arriben fins als schemas/endpoints,
    la funcionalitat és inaccessible des del panell encara que el model i
    el càlcul siguin correctes."""
    token = _admin_token(client, db)
    resp = client.patch(
        "/admin/configuracio",
        json={"recc_actiu": True, "prorrata_pct_provisional": "60.00"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["recc_actiu"] is True
    assert resp.json()["prorrata_pct_provisional"] == "60.00"

    db.refresh(db.scalar(select(ConfiguracioBotiga)))
    config = db.scalar(select(ConfiguracioBotiga))
    assert config.recc_actiu is True
    assert config.prorrata_pct_provisional == Decimal("60.00")


def test_destino_iva_i_importacio_diferida_son_configurables_via_api(client, db):
    token = _admin_token(client, db)
    resp = client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-04-10", "supplier_name": "Prov", "category": "subministraments",
            "concept": "Test", "taxable_base": "100.00", "vat_pct": "21.00",
            "destino_iva": "comu", "importacio_diferida": True,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["destino_iva"] == "comu"
    assert resp.json()["importacio_diferida"] is True

    despesa_id = resp.json()["id"]
    resp2 = client.patch(
        f"/admin/despeses/{despesa_id}", json={"destino_iva": "activitat_exempta"}, headers=_auth(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["destino_iva"] == "activitat_exempta"


def test_tipus_iva_exempt_es_configurable_via_api(client, db):
    token = _admin_token(client, db)
    resp = client.post(
        "/admin/tipus-iva", json={"name": "Exempt", "percentage": "0.00", "exempt": True}, headers=_auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["exempt"] is True
