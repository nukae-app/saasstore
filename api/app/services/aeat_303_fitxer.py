"""Generador del fitxer oficial del Model 303 (IVA trimestral), disseny de
registre `DR303e21v200.xlsx` (AEAT, Ordre HAC/646/2021, vigent des del
període 07/2021) — ver docs/PLAN_MODELO303_FITXER.md per l'abast exacte i
les caselles cobertes.

NOMÉS genera el fitxer — mai el presenta telemàticament. L'admin el puja a
mà a la Seu Electrònica. **No s'ha pogut verificar contra una presentació
real ni contra el validador oficial** — provar-ho abans de confiar-hi en
producció, mateix criteri que `services/sepa_pain001.py`.

Format de text d'ample fix (ISO-8859-1, assumit per ser el conveni habitual
dels fitxers BOE d'AEAT — verificar-ho també): camps "An" (alfanumèrics)
alineats a l'esquerra amb espais a la dreta; "Num" (numèrics sense signe)
alineats a la dreta amb zeros a l'esquerra; "N" (numèrics amb signe) igual
que "Num" però amb una "N" a la primera posició quan el valor és negatiu
(substitueix un dígit, no allarga el camp).

Pàgines cobertes: 1 (identificació + règim general 01-46), 3 (informació
addicional RECC + cascada de resultat + complementària + IBAN), i 5
(prorrata especial, NOMÉS si `ConfiguracioBotiga.prorrata_pct_provisional`
està informat — "en cas de no tenir contingut, aquesta pàgina 5 no s'ha
d'incloure", Nota 3 del disseny oficial). Pàgina 2 (règim simplificat) i 4
(exoneració del 390 + tributació foral + OSS) fora d'abast, mai incloses."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


def _an(value: str | None, length: int) -> str:
    """Alfanumèric: alineat a l'esquerra, espais a la dreta, retallat si cal."""
    return (value or "")[:length].ljust(length)


def _num(value: int, length: int) -> str:
    """Numèric sense signe: alineat a la dreta, zeros a l'esquerra."""
    return str(value)[-length:].rjust(length, "0") if value >= 0 else "0" * length


def _amount(value: Decimal | None, length: int, signed: bool = True) -> str:
    """Import amb 2 decimals implícits (sense punt): `length` inclou el
    dígit de signe quan `signed=True` i el valor és negatiu (l'"N" ocupa la
    primera posició, no allarga el camp — mateix criteri que la resta del
    disseny oficial)."""
    value = value or Decimal("0.00")
    centims = int((value * 100).to_integral_value())
    negatiu = centims < 0
    digits = str(abs(centims))
    if negatiu and signed:
        return "N" + digits.rjust(length - 1, "0")[-(length - 1):]
    return digits.rjust(length, "0")[-length:]


def _blank(length: int) -> str:
    return " " * length


PERIODES = {1: "1T", 2: "2T", 3: "3T", 4: "4T"}


@dataclass(frozen=True)
class Model303Identificacio:
    nif: str
    raho_social: str
    year: int
    trimestre: int
    tipo_declaracion: str
    recc_actiu: bool
    exonerat_390: bool = False


@dataclass(frozen=True)
class Model303Caselles:
    """Un subconjunt de `Model303Out` — només el que fa falta per codificar
    el fitxer, evita acoblar aquest mòdul a la resta de l'schema."""
    repercutit_general_base: Decimal
    repercutit_general_cuota: Decimal
    repercutit_reduit_base: Decimal
    repercutit_reduit_cuota: Decimal
    repercutit_superreduit_base: Decimal
    repercutit_superreduit_cuota: Decimal
    casella_27: Decimal
    casella_28: Decimal
    casella_29: Decimal
    casella_30: Decimal
    casella_31: Decimal
    casella_45: Decimal
    casella_46: Decimal
    casella_62: Decimal
    casella_63: Decimal
    casella_74: Decimal
    casella_75: Decimal
    casella_77: Decimal
    casella_110: Decimal


def _pagina_301(ident: Model303Identificacio, c: Model303Caselles) -> str:
    parts = [
        "<T", "303", "01000", ">",
        _blank(1),  # indicador pàgina complementària
        _an(ident.tipo_declaracion, 1),
        _an(ident.nif, 9),
        _an(ident.raho_social, 80),
        _num(ident.year, 4),
        _an(PERIODES[ident.trimestre], 2),
        "2",  # tributació exclusivament foral: NO (fora d'abast, ver docs)
        "2",  # inscrit registre devolució mensual: NO
        "3",  # tributa exclusivament règim simplificat: NO (només RG)
        "2",  # autoliquidació conjunta: NO
        "1" if ident.recc_actiu else "2",  # acollit al RECC
        "2",  # destinatari d'operacions RECC: NO (fora d'abast)
        _blank(1),  # opció prorrata especial: fora d'abast (es tracta com ja exercida en un exercici anterior)
        _blank(1),  # revocació opció prorrata especial
        "2",  # concurs de creditors en el període: NO (fora d'abast)
        _blank(8),  # data auto declaració de concurs
        _blank(1),  # auto de concurs dictat en el període
        "2",  # acollit voluntàriament al SII: NO
        ("0" if ident.trimestre != 4 else ("1" if ident.exonerat_390 else "2")),  # exonerat del 390
        "0",  # volum anual d'operacions distint de zero: només rellevant si exonerat del 390 (fora d'abast aquí)
        _amount(c.repercutit_general_base, 17), _amount(Decimal("21.00"), 5, signed=False),
        _amount(c.repercutit_general_cuota, 17),
        _amount(c.repercutit_reduit_base, 17), _amount(Decimal("10.00"), 5, signed=False),
        _amount(c.repercutit_reduit_cuota, 17),
        _amount(c.repercutit_superreduit_base, 17), _amount(Decimal("4.00"), 5, signed=False),
        _amount(c.repercutit_superreduit_cuota, 17),
        _amount(Decimal("0"), 17), _amount(Decimal("0"), 17),  # [10]/[11] adquisicions intracomunitàries: fora d'abast
        _amount(Decimal("0"), 17), _amount(Decimal("0"), 17),  # [12]/[13] altres inversió subjecte passiu: fora d'abast
        _amount(Decimal("0"), 17), _amount(Decimal("0"), 17),  # [14]/[15] modificació bases i quotes: fora d'abast
        _amount(Decimal("0"), 17), _amount(Decimal("0"), 5, signed=False), _amount(Decimal("0"), 17),  # [16]-[18] recàrrec equivalència: fora d'abast
        _amount(Decimal("0"), 17), _amount(Decimal("0"), 5, signed=False), _amount(Decimal("0"), 17),  # [19]-[21] recàrrec equivalència: fora d'abast
        _amount(Decimal("0"), 17), _amount(Decimal("0"), 5, signed=False), _amount(Decimal("0"), 17),  # [22]-[24] recàrrec equivalència: fora d'abast
        _amount(Decimal("0"), 17), _amount(Decimal("0"), 17),  # [25]/[26] modificacions recàrrec: fora d'abast
        _amount(c.casella_27, 17),
        _amount(c.casella_28, 17), _amount(c.casella_29, 17),
        _amount(c.casella_30, 17), _amount(c.casella_31, 17),
        _amount(Decimal("0"), 17), _amount(Decimal("0"), 17),  # [32]/[33] importacions corrents: fora d'abast (importació diferida va a [77], no aquí)
        _amount(Decimal("0"), 17), _amount(Decimal("0"), 17),  # [34]/[35] importacions béns d'inversió: fora d'abast
        _amount(Decimal("0"), 17), _amount(Decimal("0"), 17),  # [36]/[37] adq. intracom. corrents: fora d'abast
        _amount(Decimal("0"), 17), _amount(Decimal("0"), 17),  # [38]/[39] adq. intracom. inversió: fora d'abast
        _amount(Decimal("0"), 17), _amount(Decimal("0"), 17),  # [40]/[41] rectificació deduccions: fora d'abast
        _amount(Decimal("0"), 17),  # [42] compensacions REAGP: fora d'abast
        _amount(Decimal("0"), 17),  # [43] regularització inversions: fora d'abast
        _amount(Decimal("0"), 17),  # [44] regularització prorrata definitiva: fora d'abast (aplicat ja a 29 via % provisional)
        _amount(c.casella_45, 17),
        _amount(c.casella_46, 17),
        _blank(600),  # reservat AEAT
        _blank(13),  # reservat AEAT (segell electrònic)
        "</T30301000>",
    ]
    return "".join(parts)


def _pagina_303(
    ident: Model303Identificacio, c: Model303Caselles, *, resultat_46: Decimal,
    import_compensacio_aplicada: Decimal, es_complementaria: bool, numero_justificant_anterior: str | None,
    iban_devolucio: str | None, bic_devolucio: str | None,
) -> str:
    casella_64 = resultat_46  # [46]+[58]+[76], amb 58 (RS) i 76 (regularització impagats) sempre 0 aquí
    casella_66 = casella_64  # 100% atribuïble a l'Estat (fora d'abast tributació foral)
    casella_78 = import_compensacio_aplicada
    casella_87 = c.casella_110 - casella_78
    casella_69 = casella_66 + c.casella_77 - casella_78
    casella_71 = casella_69  # [70] "a deduir" sempre 0 (fora d'abast)

    parts = [
        "<T", "303", "03000", ">",
        _amount(Decimal("0"), 17), _amount(Decimal("0"), 17),  # [59]/[60] intracom./exportacions: fora d'abast
        _amount(Decimal("0"), 17),  # [61] no subjectes amb dret a deducció: fora d'abast
        _amount(Decimal("0"), 17),  # [120] no subjectes per regles de localització: fora d'abast
        _blank(17),  # reservat AEAT
        _amount(Decimal("0"), 17),  # [122] subjectes amb inversió subjecte passiu: fora d'abast
        _amount(Decimal("0"), 17),  # [123] OSS no subjectes: fora d'abast
        _amount(Decimal("0"), 17),  # [124] OSS subjectes: fora d'abast
        _amount(c.casella_62, 17), _amount(c.casella_63, 17),
        _amount(c.casella_74, 17), _amount(c.casella_75, 17),
        _amount(Decimal("0"), 17),  # [76] regularització art. 80.cinco.5a: fora d'abast
        _amount(casella_64, 17),
        _amount(Decimal("100.00"), 5, signed=False),  # [65] % atribuïble Estat: sempre 100 (fora d'abast foral)
        _amount(casella_66, 17),
        _amount(c.casella_77, 17),
        _amount(c.casella_110, 17),
        _amount(casella_78, 17),
        _amount(casella_87, 17),
        _amount(Decimal("0"), 17),  # [68] regularització anual foral: fora d'abast
        _amount(casella_69, 17),
        _amount(Decimal("0"), 17),  # [70] a deduir: fora d'abast
        _amount(casella_71, 17),
        ("X" if es_complementaria else _blank(1)),
        _an(numero_justificant_anterior, 13),
        ("X" if ident.tipo_declaracion == "N" else _blank(1)),
        _an(bic_devolucio, 11),
        _an(iban_devolucio, 34),
        _blank(17),  # reservat AEAT
        _blank(70), _blank(35), _blank(30), _blank(2), _blank(1),  # dades de banc estranger: fora d'abast
        _blank(445),  # reservat AEAT
        "</T30303000>",
    ]
    return "".join(parts)


def _pagina_305(prorrata_pct: Decimal, cnae_code: str, import_operacions: Decimal) -> str:
    """NOMÉS s'inclou si hi ha prorrata especial configurada (Nota 3 del
    disseny oficial: sense contingut, la pàgina 5 no s'ha d'incloure).
    Un únic bloc d'activitat (CNAE) — aquest sistema no modela múltiples
    activitats econòmiques diferenciades. `import_operacions` s'informa
    també com a "amb dret a deducció": no es modelen vendes exemptes al
    catàleg, ver docs/PLAN_MODELO303_FITXER.md."""
    parts = [
        "<T", "303", "05000", ">",
        _blank(1),  # indicador pàgina complementària
        _an(cnae_code, 3),
        _amount(import_operacions, 17, signed=False),
        _amount(import_operacions, 17, signed=False),
        "E",  # tipus de prorrata: especial
        _amount(prorrata_pct, 5, signed=False),
        # Blocs d'activitat 2-5: sense contingut (codi/tipus en blanc, imports a 0)
        *([_blank(3), _amount(Decimal("0"), 17, signed=False), _amount(Decimal("0"), 17, signed=False), _blank(1), _amount(Decimal("0"), 5, signed=False)] * 4),
        # Règim de deduccions diferides d'exercicis anteriors (13. Reg. Deducc.
        # Diferenc., 2 blocs x 18 caselles numèriques): fora d'abast, sempre 0.
        *([_amount(Decimal("0"), 17)] * 36),
        _blank(672),  # reservat AEAT
        "</T30305000>",
    ]
    return "".join(parts)


def build_model303_fitxer(
    ident: Model303Identificacio, caselles: Model303Caselles, *,
    import_compensacio_aplicada: Decimal = Decimal("0.00"), es_complementaria: bool = False,
    numero_justificant_anterior: str | None = None, iban_devolucio: str | None = None,
    bic_devolucio: str | None = None, prorrata_pct: Decimal | None = None, cnae_code: str | None = None,
    import_operacions_prorrata: Decimal = Decimal("0.00"),
) -> str:
    if prorrata_pct is not None and not cnae_code:
        raise ValueError("Cal informar el codi CNAE per generar la pàgina de prorrata especial")

    pagina1 = _pagina_301(ident, caselles)
    pagina3 = _pagina_303(
        ident, caselles, resultat_46=caselles.casella_46,
        import_compensacio_aplicada=import_compensacio_aplicada, es_complementaria=es_complementaria,
        numero_justificant_anterior=numero_justificant_anterior,
        iban_devolucio=iban_devolucio, bic_devolucio=bic_devolucio,
    )
    contingut = pagina1 + pagina3
    if prorrata_pct is not None:
        contingut += _pagina_305(prorrata_pct, cnae_code, import_operacions_prorrata)

    periode = PERIODES[ident.trimestre]
    ara = datetime.now()
    envelope = (
        "<T" + "303" + "0" + _num(ident.year, 4) + periode + "0000>"
        + "<AUX>"
        + _blank(70)  # reservat AEAT
        + _blank(4)  # versió del programa (Nota 1 — només per a entitats desenvolupadores registrades)
        + _blank(4)  # reservat AEAT
        + _blank(9)  # NIF empresa de desenvolupament (Nota 1)
        + _blank(213)  # reservat AEAT
        + "</AUX>"
        + contingut
        + f"</T3030{ident.year:04d}{periode}0000>"
    )
    return envelope
