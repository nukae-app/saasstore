"""Tests del motor de posting automàtic (Fase 2): la invariant de partida
doble (sum(debit)==sum(credit)), la numeració correlativa d'assentaments, i
que els hooks de despeses/TPV/caixa diària generin assentaments correctes."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    CanalComissio, ComissioPagament, CondicionItem, Item, JournalEntry, JournalLine, JournalSourceType,
    ModeComissio, Release, User,
)
from app.services.comptabilitat_posting import calcula_comissio, next_entry_number, post_cobrament_conciliacio, post_entry


def _seed_release(db, artista="Artista", titulo="Àlbum", formato="LP") -> Release:
    r = Release(artista=artista, title=titulo, formato=formato)
    db.add(r)
    db.commit()
    return r


def _seed_item(db, release, precio="20.00", coste="10.00", condicion=CondicionItem.nou, quantity=1) -> Item:
    item = Item(release_id=release.id, price=Decimal(precio), acquisition_cost=Decimal(coste), condition=condicion, quantity=quantity)
    db.add(item)
    db.commit()
    return item


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


def test_post_entry_desbalancejat_falla(db):
    try:
        post_entry(
            db, entry_date=date(2026, 1, 15), description="test descompensat",
            source_type=JournalSourceType.manual, source_id=None,
            lines=[("570", Decimal("10.00"), Decimal("0")), ("700", Decimal("0"), Decimal("5.00"))],
        )
        assert False, "hauria d'haver aixecat ValueError"
    except ValueError as exc:
        assert "descompensat" in str(exc)
    assert db.scalar(select(JournalEntry)) is None


def test_post_entry_numeracio_correlativa(db):
    e1 = post_entry(
        db, entry_date=date(2026, 3, 1), description="u", source_type=JournalSourceType.manual, source_id=None,
        lines=[("570", Decimal("10.00"), Decimal("0")), ("700", Decimal("0"), Decimal("10.00"))],
    )
    e2 = post_entry(
        db, entry_date=date(2026, 3, 2), description="dos", source_type=JournalSourceType.manual, source_id=None,
        lines=[("570", Decimal("5.00"), Decimal("0")), ("700", Decimal("0"), Decimal("5.00"))],
    )
    db.commit()
    assert e1.fiscal_year == 2026
    assert e1.entry_number == 1
    assert e2.entry_number == 2
    # Un any fiscal diferent arrenca el seu propi comptador, no continua el de 2026.
    assert next_entry_number(db, 2027) == 1


def test_despesa_alta_genera_assentament_balancejat(client, db):
    token = _admin_token(client, db)
    resp = client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-02-10", "supplier_name": "Endesa", "category": "subministraments",
            "concept": "Llum febrer", "taxable_base": "100.00", "vat_pct": "21.00",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    despesa_id = uuid.UUID(resp.json()["id"])

    entry = db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_type == JournalSourceType.despesa_alta, JournalEntry.source_id == despesa_id,
        )
    )
    assert entry is not None
    lines = db.scalars(select(JournalLine).where(JournalLine.entry_id == entry.id)).all()
    assert sum(l.debit for l in lines) == sum(l.credit for l in lines) == Decimal("121.00")
    codis = {l.account.code: (l.debit, l.credit) for l in lines}
    assert codis["628"] == (Decimal("100.00"), Decimal("0.00"))  # subministraments, no 300 (no es compres_material)
    assert codis["472"] == (Decimal("21.00"), Decimal("0.00"))
    assert codis["400"] == (Decimal("0.00"), Decimal("121.00"))


def test_despesa_compres_material_va_a_300_no_a_600(client, db):
    token = _admin_token(client, db)
    resp = client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-02-10", "supplier_name": "Distribuïdora", "category": "compres_material",
            "concept": "Reposició estoc", "taxable_base": "50.00", "vat_pct": "21.00",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    entry = db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_type == JournalSourceType.despesa_alta, JournalEntry.source_id == uuid.UUID(resp.json()["id"]),
        )
    )
    codis = {l.account.code for l in db.scalars(select(JournalLine).where(JournalLine.entry_id == entry.id))}
    assert "300" in codis
    assert "600" not in codis


def test_despesa_pagada_a_l_alta_genera_tambe_assentament_de_pagament(client, db):
    token = _admin_token(client, db)
    resp = client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-02-10", "supplier_name": "Papereria", "category": "material_oficina",
            "concept": "Material", "taxable_base": "10.00", "vat_pct": "21.00",
            "payment_status": "pagat", "payment_method": "efectiu", "payment_date": "2026-02-10",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    despesa_id = uuid.UUID(resp.json()["id"])

    alta = db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_type == JournalSourceType.despesa_alta, JournalEntry.source_id == despesa_id,
        )
    )
    pagament = db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_type == JournalSourceType.despesa_pagament, JournalEntry.source_id == despesa_id,
        )
    )
    assert alta is not None and pagament is not None
    pagament_lines = {l.account.code: (l.debit, l.credit) for l in db.scalars(select(JournalLine).where(JournalLine.entry_id == pagament.id))}
    assert pagament_lines["400"] == (Decimal("12.10"), Decimal("0.00"))
    assert pagament_lines["570"] == (Decimal("0.00"), Decimal("12.10"))  # efectiu -> caixa, no banc


def test_venda_tpv_amb_cost_genera_linies_610_300(client, db):
    token = _admin_token(client, db)
    release = _seed_release(db)
    item = _seed_item(db, release, precio="20.00", coste="8.00")
    resp = client.post(
        "/admin/ventas-externas",
        json={
            "item_id": str(item.id), "channel": "mostrador", "payment_method": "efectivo",
            "sale_price": "20.00", "quantity": 1, "date": "2026-04-01T10:00:00",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    venta_id = uuid.UUID(resp.json()["id"])

    entry = db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_type == JournalSourceType.venda_externa, JournalEntry.source_id == venta_id,
        )
    )
    assert entry is not None
    lines = db.scalars(select(JournalLine).where(JournalLine.entry_id == entry.id)).all()
    assert sum(l.debit for l in lines) == sum(l.credit for l in lines)
    codis = {l.account.code: (l.debit, l.credit) for l in lines}
    assert codis["430"][0] == Decimal("20.00")
    assert codis["610"] == (Decimal("8.00"), Decimal("0.00"))
    assert codis["300"] == (Decimal("0.00"), Decimal("8.00"))


def test_caixa_diaria_reeditar_no_duplica_assentaments(client, db):
    token = _admin_token(client, db)
    resp = client.put(
        "/admin/caixa-diaria/2026/5",
        json=[{"date": "2026-05-10", "cash_21": "50.00"}],
        headers=_auth(token),
    )
    assert resp.status_code == 200
    caixa_id = db.execute(
        select(JournalEntry.source_id).where(JournalEntry.source_type == JournalSourceType.caixa_diaria)
    ).scalar_one()

    resp2 = client.put(
        "/admin/caixa-diaria/2026/5",
        json=[{"date": "2026-05-10", "cash_21": "80.00"}],
        headers=_auth(token),
    )
    assert resp2.status_code == 200

    entries = db.scalars(
        select(JournalEntry).where(
            JournalEntry.source_type == JournalSourceType.caixa_diaria, JournalEntry.source_id == caixa_id,
        )
    ).all()
    assert len(entries) == 1
    lines = {l.account.code: (l.debit, l.credit) for l in db.scalars(select(JournalLine).where(JournalLine.entry_id == entries[0].id))}
    assert lines["570"] == (Decimal("80.00"), Decimal("0.00"))
    assert lines["430"] == (Decimal("0.00"), Decimal("80.00"))


def test_calcula_comissio_sense_config_retorna_zero(db):
    assert calcula_comissio(db, CanalComissio.web_targeta, Decimal("100.00")) == Decimal("0.00")


def test_calcula_comissio_mode_deduccio_aplica_pct_i_fixed_fee(db):
    db.add(ComissioPagament(
        canal=CanalComissio.web_targeta, mode=ModeComissio.deduccio,
        pct=Decimal("0.30"), fixed_fee=Decimal("0.10"),
    ))
    db.commit()
    # 100.00 * 0.30% + 0.10 = 0.40
    assert calcula_comissio(db, CanalComissio.web_targeta, Decimal("100.00")) == Decimal("0.40")


def test_calcula_comissio_mode_cobrament_apart_retorna_zero(db):
    """En aquest mode el banc ingressa l'import íntegre; la comissió es
    factura a part com una Despesa normal — no toca cap tancament."""
    db.add(ComissioPagament(
        canal=CanalComissio.mostrador_targeta, mode=ModeComissio.cobrament_apart,
        pct=Decimal("1.00"), fixed_fee=Decimal("0.00"),
    ))
    db.commit()
    assert calcula_comissio(db, CanalComissio.mostrador_targeta, Decimal("100.00")) == Decimal("0.00")


def test_calcula_comissio_inactiva_es_ignora(db):
    db.add(ComissioPagament(
        canal=CanalComissio.web_targeta, mode=ModeComissio.deduccio,
        pct=Decimal("5.00"), fixed_fee=Decimal("0.00"), active=False,
    ))
    db.commit()
    assert calcula_comissio(db, CanalComissio.web_targeta, Decimal("100.00")) == Decimal("0.00")


def test_post_cobrament_conciliacio_amb_comissio_genera_626(db):
    entry = post_cobrament_conciliacio(
        db, entry_date=date(2026, 6, 1), source_type=JournalSourceType.venda_web, source_id=uuid.uuid4(),
        amount=Decimal("100.00"), comissio=Decimal("0.40"), description="test comissió",
    )
    db.commit()
    lines = {l.account.code: (l.debit, l.credit) for l in db.scalars(select(JournalLine).where(JournalLine.entry_id == entry.id))}
    assert lines["572"] == (Decimal("99.60"), Decimal("0.00"))
    assert lines["626"] == (Decimal("0.40"), Decimal("0.00"))
    assert lines["430"] == (Decimal("0.00"), Decimal("100.00"))


def test_post_cobrament_conciliacio_sense_comissio_no_toca_626(db):
    entry = post_cobrament_conciliacio(
        db, entry_date=date(2026, 6, 1), source_type=JournalSourceType.venda_web, source_id=uuid.uuid4(),
        amount=Decimal("50.00"), description="test sense comissió",
    )
    db.commit()
    codis = {l.account.code for l in db.scalars(select(JournalLine).where(JournalLine.entry_id == entry.id))}
    assert codis == {"572", "430"}


def test_caixa_diaria_amb_comissio_targeta_mostrador_genera_626(client, db):
    db.add(ComissioPagament(
        canal=CanalComissio.mostrador_targeta, mode=ModeComissio.deduccio,
        pct=Decimal("1.00"), fixed_fee=Decimal("0.00"),
    ))
    db.commit()
    token = _admin_token(client, db)
    resp = client.put(
        "/admin/caixa-diaria/2026/7",
        json=[{"date": "2026-07-05", "card_21": "100.00", "cash_21": "20.00"}],
        headers=_auth(token),
    )
    assert resp.status_code == 200

    entry = db.scalar(select(JournalEntry).where(JournalEntry.source_type == JournalSourceType.caixa_diaria))
    lines = {l.account.code: (l.debit, l.credit) for l in db.scalars(select(JournalLine).where(JournalLine.entry_id == entry.id))}
    # 100.00 de targeta amb 1% de comissió (1.00) -> 99.00 net + 20.00 efectiu = 119.00 a tresoreria
    assert lines["570"] == (Decimal("20.00"), Decimal("0.00"))
    assert lines["572"] == (Decimal("99.00"), Decimal("0.00"))
    assert lines["626"] == (Decimal("1.00"), Decimal("0.00"))
    assert lines["430"] == (Decimal("0.00"), Decimal("120.00"))


def test_caixa_diaria_sense_comissio_configurada_es_comporta_igual_que_abans(client, db):
    token = _admin_token(client, db)
    resp = client.put(
        "/admin/caixa-diaria/2026/8",
        json=[{"date": "2026-08-05", "card_21": "100.00", "bizum_21": "10.00"}],
        headers=_auth(token),
    )
    assert resp.status_code == 200
    entry = db.scalar(select(JournalEntry).where(JournalEntry.source_type == JournalSourceType.caixa_diaria))
    lines = {l.account.code: (l.debit, l.credit) for l in db.scalars(select(JournalLine).where(JournalLine.entry_id == entry.id))}
    assert lines["572"] == (Decimal("110.00"), Decimal("0.00"))
    assert "626" not in lines
    assert lines["430"] == (Decimal("0.00"), Decimal("110.00"))


def test_comissions_pagament_crud(client, db):
    token = _admin_token(client, db)
    resp = client.post(
        "/admin/comissions-pagament",
        json={"canal": "web_targeta", "mode": "deduccio", "pct": "0.30", "fixed_fee": "0.10"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    comissio_id = resp.json()["id"]

    # No es pot duplicar canal
    dup = client.post(
        "/admin/comissions-pagament",
        json={"canal": "web_targeta", "mode": "cobrament_apart", "pct": "0", "fixed_fee": "0"},
        headers=_auth(token),
    )
    assert dup.status_code == 409

    llistat = client.get("/admin/comissions-pagament", headers=_auth(token))
    assert llistat.status_code == 200 and len(llistat.json()) == 1

    patch = client.patch(
        f"/admin/comissions-pagament/{comissio_id}",
        json={"canal": "web_targeta", "mode": "cobrament_apart", "pct": "0", "fixed_fee": "0", "active": True},
        headers=_auth(token),
    )
    assert patch.status_code == 200 and patch.json()["mode"] == "cobrament_apart"

    assert client.delete(f"/admin/comissions-pagament/{comissio_id}", headers=_auth(token)).status_code == 204
    assert client.get("/admin/comissions-pagament", headers=_auth(token)).json() == []
