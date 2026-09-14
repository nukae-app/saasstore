"""Tests del codificador del fitxer oficial AEAT Model 303 — longituds
exactes contra el disseny de registre real (DR303e21v200.xlsx, Ordre
HAC/646/2021), ver docs/PLAN_MODELO303_FITXER.md."""

from decimal import Decimal

import pytest

from app.services.aeat_303_fitxer import (
    Model303Caselles, Model303Identificacio, _amount, _pagina_301, _pagina_303, _pagina_305, build_model303_fitxer,
)

LONGITUD_PAGINA_301 = 1464
LONGITUD_PAGINA_303 = 1079
LONGITUD_PAGINA_305 = 1523


def _ident(**overrides) -> Model303Identificacio:
    base = dict(
        nif="B12345678", raho_social="Ultra-Local Records SL", year=2026, trimestre=3,
        tipo_declaracion="I", recc_actiu=False,
    )
    base.update(overrides)
    return Model303Identificacio(**base)


def _caselles(**overrides) -> Model303Caselles:
    base = dict(
        repercutit_general_base=Decimal("1000.00"), repercutit_general_cuota=Decimal("210.00"),
        repercutit_reduit_base=Decimal("0"), repercutit_reduit_cuota=Decimal("0"),
        repercutit_superreduit_base=Decimal("0"), repercutit_superreduit_cuota=Decimal("0"),
        casella_27=Decimal("210.00"), casella_28=Decimal("500.00"), casella_29=Decimal("105.00"),
        casella_30=Decimal("0"), casella_31=Decimal("0"), casella_45=Decimal("105.00"),
        casella_46=Decimal("105.00"), casella_62=Decimal("0"), casella_63=Decimal("0"),
        casella_74=Decimal("0"), casella_75=Decimal("0"), casella_77=Decimal("0"), casella_110=Decimal("0"),
    )
    base.update(overrides)
    return Model303Caselles(**base)


def test_amount_positiu_sense_signe():
    assert _amount(Decimal("123.45"), 17) == "00000000000012345"


def test_amount_negatiu_usa_n_a_la_primera_posicio():
    valor = _amount(Decimal("-123.45"), 17)
    assert valor[0] == "N"
    assert len(valor) == 17
    assert valor == "N0000000000012345"


def test_amount_unsigned_ignora_signe():
    assert _amount(Decimal("21.00"), 5, signed=False) == "02100"


def test_pagina_301_longitud_exacta():
    assert len(_pagina_301(_ident(), _caselles())) == LONGITUD_PAGINA_301


def test_pagina_303_longitud_exacta():
    p = _pagina_303(
        _ident(), _caselles(), resultat_46=Decimal("105.00"), import_compensacio_aplicada=Decimal("0"),
        es_complementaria=False, numero_justificant_anterior=None, iban_devolucio=None, bic_devolucio=None,
    )
    assert len(p) == LONGITUD_PAGINA_303


def test_pagina_305_longitud_exacta():
    assert len(_pagina_305(Decimal("50.00"), "476", Decimal("1000.00"))) == LONGITUD_PAGINA_305


def test_pagina_301_conte_nif_i_periode():
    p = _pagina_301(_ident(nif="B87654321"), _caselles())
    assert "B87654321" in p
    assert p[106:108] == "3T"  # posició 107 (1-indexed) = període


def test_pagina_301_marca_recc_quan_actiu():
    p_actiu = _pagina_301(_ident(recc_actiu=True), _caselles())
    p_inactiu = _pagina_301(_ident(recc_actiu=False), _caselles())
    assert p_actiu[112] == "1"  # posició 113 (1-indexed) = acollit RECC
    assert p_inactiu[112] == "2"


def test_build_model303_fitxer_sense_prorrata_no_inclou_pagina_5():
    fitxer = build_model303_fitxer(_ident(), _caselles())
    assert "<T30305000>" not in fitxer


def test_build_model303_fitxer_amb_prorrata_inclou_pagina_5():
    fitxer = build_model303_fitxer(_ident(), _caselles(), prorrata_pct=Decimal("50.00"), cnae_code="476")
    assert "<T30305000>" in fitxer


def test_build_model303_fitxer_prorrata_sense_cnae_falla():
    with pytest.raises(ValueError):
        build_model303_fitxer(_ident(), _caselles(), prorrata_pct=Decimal("50.00"), cnae_code=None)


def test_build_model303_fitxer_longitud_total_es_suma_de_pagines():
    fitxer_sense_prorrata = build_model303_fitxer(_ident(), _caselles())
    fitxer_amb_prorrata = build_model303_fitxer(
        _ident(), _caselles(), prorrata_pct=Decimal("50.00"), cnae_code="476"
    )
    assert len(fitxer_amb_prorrata) - len(fitxer_sense_prorrata) == LONGITUD_PAGINA_305
