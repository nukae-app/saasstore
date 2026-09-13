"""Tests del generador del fitxer SEPA pain.001.001.03 (transferència a
proveïdors) — ver docs/PLAN_COBRAMENTS_PAGAMENTS.md."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.services.sepa_pain001 import Pain001Linia, _sepa_text, build_pain001_xml, generate_end_to_end_id


def test_sepa_text_translitera_accents_i_filtra_caracters_no_permesos():
    assert _sepa_text("Distribuïdora Ñoño & Cía, S.L.", 70) == "Distribuidora Nono Cia, S.L."


def test_sepa_text_retalla_a_max_len():
    assert len(_sepa_text("a" * 100, 35)) == 35


def test_sepa_text_buit_retorna_na():
    assert _sepa_text("!!!", 35) == "NA"


def test_generate_end_to_end_id_unic_per_posicio():
    a = generate_end_to_end_id("2026-0001", 1)
    b = generate_end_to_end_id("2026-0001", 2)
    assert a != b
    assert len(a) <= 35 and len(b) <= 35


def test_build_pain001_sense_linies_falla():
    with pytest.raises(ValueError):
        build_pain001_xml(
            remesa_number="2026-0001", execution_date=date(2026, 9, 20), created_at=datetime(2026, 9, 13, 10, 0),
            debtor_name="Ultra-Local Records", debtor_iban="ES9121000418450200051332", debtor_bic=None, lines=[],
        )


def test_build_pain001_estructura_i_imports():
    linies = [
        Pain001Linia(
            end_to_end_id="REM2026-0001-0001", amount=Decimal("100.00"), creditor_name="Distribuïdora Ñoño",
            creditor_iban="ES7620770024003102575766", remittance_info="Factura F-001",
        ),
        Pain001Linia(
            end_to_end_id="REM2026-0001-0002", amount=Decimal("23.45"), creditor_name="Altre Proveïdor",
            creditor_iban="ES1000492352082414205416", remittance_info="Factura F-002",
        ),
    ]
    xml = build_pain001_xml(
        remesa_number="2026-0001", execution_date=date(2026, 9, 20), created_at=datetime(2026, 9, 13, 10, 0),
        debtor_name="Ultra-Local Records SL", debtor_iban="ES91 2100 0418 4502 0005 1332", debtor_bic="CAIXESBBXXX",
        lines=linies,
    )
    assert xml.startswith("<?xml")
    assert "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03" in xml
    assert "<NbOfTxs>2</NbOfTxs>" in xml
    assert "<CtrlSum>123.45</CtrlSum>" in xml
    assert "<IBAN>ES9121000418450200051332</IBAN>" in xml  # sense espais
    assert "<BIC>CAIXESBBXXX</BIC>" in xml
    assert "<InstdAmt Ccy=\"EUR\">100.00</InstdAmt>" in xml
    assert "Distribuidora Nono" in xml  # translliterat, sense ï ni ñ
    assert "<ReqdExctnDt>2026-09-20</ReqdExctnDt>" in xml
    assert "<PmtMtd>TRF</PmtMtd>" in xml


def test_build_pain001_sense_bic_usa_notprovided():
    xml = build_pain001_xml(
        remesa_number="2026-0002", execution_date=date(2026, 9, 20), created_at=datetime(2026, 9, 13, 10, 0),
        debtor_name="Ultra-Local Records", debtor_iban="ES9121000418450200051332", debtor_bic=None,
        lines=[Pain001Linia(
            end_to_end_id="REM2026-0002-0001", amount=Decimal("10.00"), creditor_name="Proveïdor",
            creditor_iban="ES7620770024003102575766", remittance_info="F-1",
        )],
    )
    assert "<DbtrAgt><FinInstnId><Othr><Id>NOTPROVIDED</Id></Othr></FinInstnId></DbtrAgt>" in xml
    assert "<BIC>" not in xml
