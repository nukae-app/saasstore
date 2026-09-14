"""Caselles dels models AEAT que aquest negoci pot necessitar (IVA trimestral/anual,
retencions d'IRPF a proveïdors) — per a la majoria, NO genera cap fitxer oficial de
presentació: números per copiar a mà a la seu electrònica o passar a la gestoria; res
d'això substitueix la validació amb una gestoria real. **Excepció: el Model 303 SÍ té
generador de fitxer oficial** (`GET /aeat/303/{year}/{trimestre}/fitxer`, ver
`services/aeat_303_fitxer.py` i docs/PLAN_MODELO303_FITXER.md) — no verificat contra
una presentació real, provar-lo contra el validador de la Seu Electrònica abans de
confiar-hi en producció.

Fora d'abast deliberat a TOTS els models d'aquest fitxer excepte el 303: intracomunitàries,
importacions, prorrata, compensació de quotes/exercicis anteriors (el 303 sí els cobreix,
ver docs/PLAN_MODELO303_FITXER.md per l'abast exacte). A més, als models
de retenció (111/115): rendiments del treball (nòmines) — aquest negoci no modela
empleats, ver docs/PLAN_PARIDAD_HOLDED.md bloc "RR.HH./Nóminas"."""

import io
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import extract, select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import (
    AccountType, ConfiguracioBotiga, Despesa, DestinoIva, EstatPagamentDespesa, FixedAsset, Item,
    IvaCompensacioPendent, Order, OrderItem, OrderStatus, Proveedor, RetencioTipus, VentaExterna,
)
from ...schemas import (
    Model130Out, Model200Out, Model202Out, Model303FitxerIn, Model303Out, Model303TipusOut, Model390Out,
    Model390TrimestreOut, ModelRetencioAnualOut, ModelRetencioOut, ModelRetencioTrimestreOut, RetencioProveidorOut,
)
from ...services.aeat_303_fitxer import Model303Caselles, Model303Identificacio, build_model303_fitxer
from ...services.security import require_admin
from .llibres import _fi_de_mes, _saldos_per_tipus

router = APIRouter(prefix="/admin", tags=["comptabilitat"], dependencies=[Depends(require_admin)])

TRAMS_OFICIALS = {Decimal("21.00"): "general", Decimal("10.00"): "reduit", Decimal("4.00"): "superreduit"}


def _calcula_303(db: Session, year: int, trimestre: int) -> Model303Out:
    mesos = [(trimestre - 1) * 3 + i for i in range(1, 4)]
    config = db.scalar(select(ConfiguracioBotiga))
    recc_actiu = bool(config and config.recc_actiu)
    prorrata_pct = (config.prorrata_pct_provisional if config and config.prorrata_pct_provisional else None)

    def _in_trimestre(col):
        return (extract("year", col) == year) & (extract("month", col).in_(mesos))

    # --- IVA repercutit (01-09/27) — mateixa font que iva_trimestral existent.
    # Sota RECC, la data efectiva és la de cobrament real (Order.paid_at /
    # VentaExterna.paid_at, ja existents) en comptes de la d'emissió —
    # aquest negoci sempre cobra abans d'entregar, així que la meritació
    # forçosa als 31/12 de l'any següent (art. 163 terdecies LIVA) no pot
    # arribar a donar-se pel costat de vendes, ver docs/PLAN_MODELO303_FITXER.md ---
    data_web = Order.paid_at if recc_actiu else Order.created_at
    data_ve = VentaExterna.paid_at if recc_actiu else VentaExterna.date

    web_rows = db.execute(
        select(OrderItem.vat_pct, OrderItem.price, OrderItem.quantity, OrderItem.vat_amount)
        .join(Order, Order.id == OrderItem.order_id)
        .where(_in_trimestre(data_web))
        .where(Order.status.in_([OrderStatus.pagado, OrderStatus.enviado, OrderStatus.entregado]))
    ).all()
    ve_rows = db.execute(
        select(VentaExterna.vat_pct, VentaExterna.sale_price, VentaExterna.vat_amount)
        .where(_in_trimestre(data_ve))
    ).all()

    trams: dict[Decimal, list[Decimal]] = {}

    def _acumula(pct: Decimal | None, preu_total: Decimal, iva_import: Decimal | None) -> None:
        pct_efectiu = pct if pct is not None else Decimal("21.00")
        if iva_import is None:
            iva_import = (preu_total * pct_efectiu / (Decimal("100") + pct_efectiu)).quantize(Decimal("0.01"))
        acc = trams.setdefault(pct_efectiu, [Decimal("0"), Decimal("0")])
        acc[0] += preu_total - iva_import
        acc[1] += iva_import

    for pct, price, quantity, vat_amount in web_rows:
        _acumula(pct, price * quantity, vat_amount)
    for pct, sale_price, vat_amount in ve_rows:
        _acumula(pct, sale_price, vat_amount)

    def _tram(pct: Decimal) -> Model303TipusOut | None:
        vals = trams.get(pct)
        return Model303TipusOut(pct=pct, base=vals[0], cuota=vals[1]) if vals else None

    altres = [
        Model303TipusOut(pct=pct, base=vals[0], cuota=vals[1])
        for pct, vals in trams.items() if pct not in TRAMS_OFICIALS
    ]
    casella_27 = sum((v[1] for k, v in trams.items()), Decimal("0"))

    # --- IVA suportat corrent (28/29) — totes les Despesa que no siguin
    # d'importació diferida (van a 77, ver més avall), mai un actiu.
    # Sota RECC, només compta el que ja s'ha pagat de veritat (payment_date),
    # més la meritació forçosa de despeses de l'any anterior encara no
    # pagades al tancar el 4t trimestre de l'any en curs.
    query_corrent = select(
        Despesa.taxable_base, Despesa.vat_amount, Despesa.destino_iva,
    ).where(Despesa.importacio_diferida == False)  # noqa: E712

    if recc_actiu:
        condicio_normal = _in_trimestre(Despesa.payment_date) & (Despesa.payment_status == EstatPagamentDespesa.pagat)
        if trimestre == 4:
            meritacio_forcosa = (
                (extract("year", Despesa.invoice_date) == year - 1)
                & (Despesa.payment_status != EstatPagamentDespesa.pagat)
            )
            query_corrent = query_corrent.where(condicio_normal | meritacio_forcosa)
        else:
            query_corrent = query_corrent.where(condicio_normal)
    else:
        query_corrent = query_corrent.where(_in_trimestre(Despesa.invoice_date))

    corrent = db.execute(query_corrent).all()
    casella_28 = sum((r[0] for r in corrent), Decimal("0"))
    # Prorrata especial (art. 103.Dos.1º LIVA): activitat_gravada es dedueix
    # al 100%, activitat_exempta al 0%, comu al % provisional configurat.
    # Sense prorrata_pct_provisional informat, comú es tracta com gravat
    # (comportament actual, deducció 100%) — no s'assumeix cap prorrata sense
    # que l'usuari l'hagi configurat expressament.
    casella_29 = Decimal("0.00")
    for base, vat_amount, destino in corrent:
        quota = vat_amount or Decimal("0")
        if destino == DestinoIva.activitat_exempta:
            continue
        if destino == DestinoIva.comu and prorrata_pct is not None:
            quota = (quota * prorrata_pct / 100).quantize(Decimal("0.01"))
        casella_29 += quota

    # --- IVA a la importació diferit (77) — Despesa.importacio_diferida=True,
    # autoliquidat en aquesta mateixa declaració, mai a 28/29.
    importacio = db.execute(
        select(Despesa.vat_amount)
        .where(Despesa.importacio_diferida == True)  # noqa: E712
        .where(_in_trimestre(Despesa.invoice_date))
    ).all()
    casella_77 = sum((r[0] or Decimal("0") for r in importacio), Decimal("0"))

    # --- IVA suportat béns d'inversió (30/31) — actius fixos donats d'alta al trimestre ---
    inversio = db.execute(
        select(FixedAsset.acquisition_cost, FixedAsset.vat_amount).where(_in_trimestre(FixedAsset.acquisition_date))
    ).all()
    casella_30 = sum((r[0] for r in inversio), Decimal("0"))
    casella_31 = sum((r[1] or Decimal("0") for r in inversio), Decimal("0"))

    casella_45 = casella_29 + casella_31
    casella_46 = casella_27 - casella_45

    # --- RECC: desglossat purament informatiu (62/63/74/75) — quan actiu,
    # TOTES les operacions del tenant ho són, així que coincideix amb el que
    # ja s'ha comptat a 27/28-29.
    if recc_actiu:
        casella_62 = sum((v[0] for v in trams.values()), Decimal("0"))
        casella_63 = casella_27
        casella_74 = casella_28
        casella_75 = casella_29
    else:
        casella_62 = casella_63 = casella_74 = casella_75 = Decimal("0.00")

    # --- Compensació de quotes pendents d'exercicis anteriors (110) — el
    # que ja hi havia pendent EN ENTRAR a aquest trimestre (trimestre - 1,
    # o el 4t de l'any anterior si és el 1r trimestre).
    trimestre_anterior, any_anterior = (4, year - 1) if trimestre == 1 else (trimestre - 1, year)
    pendent = db.scalar(
        select(IvaCompensacioPendent.import_pendent).where(
            IvaCompensacioPendent.fiscal_year == any_anterior, IvaCompensacioPendent.trimestre == trimestre_anterior,
        )
    )
    casella_110 = pendent or Decimal("0.00")

    hay_rebu = db.execute(
        select(VentaExterna)
        .join(Item, Item.id == VentaExterna.item_id)
        .where(_in_trimestre(VentaExterna.date))
        .where(Item.rebu == True)
        .limit(1)
    ).first() is not None

    return Model303Out(
        year=year, trimestre=trimestre, mesos=mesos,
        repercutit_general=_tram(Decimal("21.00")), repercutit_reduit=_tram(Decimal("10.00")),
        repercutit_superreduit=_tram(Decimal("4.00")), altres_tipus_repercutit=altres,
        casella_27_cuota_meritada=casella_27,
        casella_28_base_corrent=casella_28, casella_29_cuota_corrent=casella_29,
        casella_30_base_inversio=casella_30, casella_31_cuota_inversio=casella_31,
        casella_45_total_a_deduir=casella_45,
        casella_46_resultat_regim_general=casella_46, casella_64_resultat_liquidacio=casella_46,
        casella_62_devengat_recc=casella_62, casella_63_cuota_recc=casella_63,
        casella_74_base_recc_suportat=casella_74, casella_75_cuota_recc_suportat=casella_75,
        casella_77_iva_importacio_diferit=casella_77,
        casella_110_compensacio_pendent_anterior=casella_110,
        nota_rebu=hay_rebu,
    )


@router.get("/aeat/303/{year}/{trimestre}", response_model=Model303Out)
def model_303(year: int, trimestre: int, db: Session = Depends(get_db)):
    if not (1 <= trimestre <= 4):
        raise HTTPException(422, "Trimestre ha de ser entre 1 i 4")
    return _calcula_303(db, year, trimestre)


@router.post("/aeat/303/{year}/{trimestre}/fitxer")
def generar_fitxer_303(year: int, trimestre: int, payload: Model303FitxerIn, db: Session = Depends(get_db)):
    """Genera el fitxer oficial `<T303...>` per pujar a la Seu Electrònica —
    NO el presenta telemàticament. Ver services/aeat_303_fitxer.py per
    l'abast exacte i l'avís de "no verificat contra una presentació real".

    Efecte secundari: desa/actualitza `IvaCompensacioPendent` d'aquest
    trimestre amb la casella [87] resultant, perquè el trimestre següent la
    trobi com a la seva [110] — per això és POST i no GET (a diferència de
    la resta de models AEAT, purament de lectura)."""
    if not (1 <= trimestre <= 4):
        raise HTTPException(422, "Trimestre ha de ser entre 1 i 4")

    config = db.scalar(select(ConfiguracioBotiga))
    if config is None or not config.nif:
        raise HTTPException(422, "Cal informar el NIF a la configuració de la botiga abans de generar el fitxer")

    calc = _calcula_303(db, year, trimestre)

    if payload.import_compensacio_aplicada < 0 or payload.import_compensacio_aplicada > calc.casella_110_compensacio_pendent_anterior:
        raise HTTPException(
            422,
            f"L'import de compensació aplicada ha d'estar entre 0 i la casella 110 pendent "
            f"({calc.casella_110_compensacio_pendent_anterior})",
        )

    prorrata_pct = config.prorrata_pct_provisional
    if prorrata_pct is not None and not payload.cnae_code:
        raise HTTPException(422, "Cal informar el codi CNAE (prorrata especial configurada) per generar el fitxer")

    ident = Model303Identificacio(
        nif=config.nif, raho_social=config.fiscal_name, year=year, trimestre=trimestre,
        tipo_declaracion=payload.tipo_declaracion, recc_actiu=config.recc_actiu,
    )
    caselles = Model303Caselles(
        repercutit_general_base=calc.repercutit_general.base if calc.repercutit_general else Decimal("0.00"),
        repercutit_general_cuota=calc.repercutit_general.cuota if calc.repercutit_general else Decimal("0.00"),
        repercutit_reduit_base=calc.repercutit_reduit.base if calc.repercutit_reduit else Decimal("0.00"),
        repercutit_reduit_cuota=calc.repercutit_reduit.cuota if calc.repercutit_reduit else Decimal("0.00"),
        repercutit_superreduit_base=calc.repercutit_superreduit.base if calc.repercutit_superreduit else Decimal("0.00"),
        repercutit_superreduit_cuota=calc.repercutit_superreduit.cuota if calc.repercutit_superreduit else Decimal("0.00"),
        casella_27=calc.casella_27_cuota_meritada,
        casella_28=calc.casella_28_base_corrent, casella_29=calc.casella_29_cuota_corrent,
        casella_30=calc.casella_30_base_inversio, casella_31=calc.casella_31_cuota_inversio,
        casella_45=calc.casella_45_total_a_deduir, casella_46=calc.casella_46_resultat_regim_general,
        casella_62=calc.casella_62_devengat_recc, casella_63=calc.casella_63_cuota_recc,
        casella_74=calc.casella_74_base_recc_suportat, casella_75=calc.casella_75_cuota_recc_suportat,
        casella_77=calc.casella_77_iva_importacio_diferit, casella_110=calc.casella_110_compensacio_pendent_anterior,
    )

    fitxer = build_model303_fitxer(
        ident, caselles,
        import_compensacio_aplicada=payload.import_compensacio_aplicada, es_complementaria=payload.es_complementaria,
        numero_justificant_anterior=payload.numero_justificante_anterior,
        iban_devolucio=payload.iban_devolucio, bic_devolucio=payload.bic_devolucio,
        prorrata_pct=prorrata_pct, cnae_code=payload.cnae_code,
        import_operacions_prorrata=caselles.casella_27 + caselles.casella_28,
    )

    casella_87 = calc.casella_110_compensacio_pendent_anterior - payload.import_compensacio_aplicada
    pendent = db.scalar(
        select(IvaCompensacioPendent).where(
            IvaCompensacioPendent.fiscal_year == year, IvaCompensacioPendent.trimestre == trimestre,
        )
    )
    if pendent is None:
        pendent = IvaCompensacioPendent(fiscal_year=year, trimestre=trimestre, import_pendent=casella_87)
        db.add(pendent)
    else:
        pendent.import_pendent = casella_87
    db.commit()

    filename = f"303_{year}_{trimestre}T.txt"
    return StreamingResponse(
        io.BytesIO(fitxer.encode("iso-8859-1", errors="replace")), media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/aeat/390/{year}", response_model=Model390Out)
def model_390(year: int, db: Session = Depends(get_db)):
    """Resum anual de l'IVA: agrega els 4 trimestres del Model 303 amb la
    mateixa font de dades, sense recalcular res de nou."""
    trimestres = [_calcula_303(db, year, t) for t in range(1, 5)]
    return Model390Out(
        year=year,
        trimestres=[
            Model390TrimestreOut(
                trimestre=t.trimestre,
                casella_27_cuota_meritada=t.casella_27_cuota_meritada,
                casella_45_total_a_deduir=t.casella_45_total_a_deduir,
                resultat=t.casella_64_resultat_liquidacio,
            )
            for t in trimestres
        ],
        casella_27_cuota_meritada_anual=sum((t.casella_27_cuota_meritada for t in trimestres), Decimal("0")),
        casella_45_total_a_deduir_anual=sum((t.casella_45_total_a_deduir for t in trimestres), Decimal("0")),
        resultat_anual=sum((t.casella_64_resultat_liquidacio for t in trimestres), Decimal("0")),
        nota_rebu=any(t.nota_rebu for t in trimestres),
    )


def _desglossat_retencions(
    db: Session, data_des_de: date, data_fins: date, tipus: RetencioTipus,
) -> list[RetencioProveidorOut]:
    """Agregació per proveïdor entre dues dates — compartida pels informes
    trimestrals (111/115) i anuals (190/180): mateix criteri, diferent rang."""
    rows = db.execute(
        select(Despesa.proveidor_id, Despesa.supplier_name, Despesa.taxable_base, Despesa.retencio_import)
        .where(Despesa.invoice_date >= data_des_de, Despesa.invoice_date <= data_fins)
        .where(Despesa.retencio_tipus == tipus)
    ).all()

    nifs: dict[uuid.UUID | None, str | None] = {}
    proveidor_ids = {r[0] for r in rows if r[0] is not None}
    if proveidor_ids:
        for prov in db.scalars(select(Proveedor).where(Proveedor.id.in_(proveidor_ids))).all():
            nifs[prov.id] = prov.nif

    per_proveidor: dict[tuple[uuid.UUID | None, str], list[Decimal]] = {}
    for proveidor_id, supplier_name, base, retencio in rows:
        clau = (proveidor_id, supplier_name)
        acc = per_proveidor.setdefault(clau, [Decimal("0"), Decimal("0")])
        acc[0] += base
        acc[1] += retencio or Decimal("0")

    return [
        RetencioProveidorOut(
            proveidor_id=proveidor_id, nom=nom, nif=nifs.get(proveidor_id), base=vals[0], retencio=vals[1],
        )
        for (proveidor_id, nom), vals in per_proveidor.items()
    ]


def _calcula_retencions(db: Session, year: int, trimestre: int, tipus: RetencioTipus) -> ModelRetencioOut:
    mesos = [(trimestre - 1) * 3 + i for i in range(1, 4)]
    desglossat = _desglossat_retencions(db, date(year, mesos[0], 1), _fi_de_mes(year, mesos[-1]), tipus)
    return ModelRetencioOut(
        year=year, trimestre=trimestre, mesos=mesos,
        num_perceptors=len(desglossat),
        base_total=sum((d.base for d in desglossat), Decimal("0")),
        retencio_total=sum((d.retencio for d in desglossat), Decimal("0")),
        desglossat=desglossat,
    )


@router.get("/aeat/111/{year}/{trimestre}", response_model=ModelRetencioOut)
def model_111(year: int, trimestre: int, db: Session = Depends(get_db)):
    """Retencions d'IRPF sobre factures de professionals (Despesa.retencio_tipus=professional)."""
    if not (1 <= trimestre <= 4):
        raise HTTPException(422, "Trimestre ha de ser entre 1 i 4")
    return _calcula_retencions(db, year, trimestre, RetencioTipus.professional)


@router.get("/aeat/115/{year}/{trimestre}", response_model=ModelRetencioOut)
def model_115(year: int, trimestre: int, db: Session = Depends(get_db)):
    """Retencions d'IRPF sobre lloguer del local (Despesa.retencio_tipus=lloguer)."""
    if not (1 <= trimestre <= 4):
        raise HTTPException(422, "Trimestre ha de ser entre 1 i 4")
    return _calcula_retencions(db, year, trimestre, RetencioTipus.lloguer)


def _calcula_retencions_anual(db: Session, year: int, tipus: RetencioTipus) -> ModelRetencioAnualOut:
    """Resum anual (190 sobre 111, 180 sobre 115): agrega tot l'any per
    proveïdor en una sola consulta (no suma els 4 trimestres per separat) —
    un mateix proveïdor amb factures en dos trimestres ha de comptar com UN
    sol perceptor a l'any, no dos."""
    trimestres = []
    for t in range(1, 5):
        desglossat_t = _desglossat_retencions(db, date(year, (t - 1) * 3 + 1, 1), _fi_de_mes(year, (t - 1) * 3 + 3), tipus)
        trimestres.append(ModelRetencioTrimestreOut(
            trimestre=t,
            base_total=sum((d.base for d in desglossat_t), Decimal("0.00")),
            retencio_total=sum((d.retencio for d in desglossat_t), Decimal("0.00")),
        ))
    desglossat = _desglossat_retencions(db, date(year, 1, 1), date(year, 12, 31), tipus)
    return ModelRetencioAnualOut(
        year=year, trimestres=trimestres,
        num_perceptors=len(desglossat),
        base_total=sum((d.base for d in desglossat), Decimal("0")),
        retencio_total=sum((d.retencio for d in desglossat), Decimal("0")),
        desglossat=desglossat,
    )


@router.get("/aeat/190/{year}", response_model=ModelRetencioAnualOut)
def model_190(year: int, db: Session = Depends(get_db)):
    """Resum anual de retencions a professionals (agrega el Model 111)."""
    return _calcula_retencions_anual(db, year, RetencioTipus.professional)


@router.get("/aeat/180/{year}", response_model=ModelRetencioAnualOut)
def model_180(year: int, db: Session = Depends(get_db)):
    """Resum anual de la retenció de lloguer (agrega el Model 115)."""
    return _calcula_retencions_anual(db, year, RetencioTipus.lloguer)


REDUCCIO_5PCT_TOPALL_ANUAL = Decimal("2000.00")


def _calcula_130(db: Session, year: int, trimestre: int, aplicar_reduccio_5pct: bool) -> Model130Out:
    """Acumulat des de l'1 de gener fins al final del trimestre (no només el
    trimestre, a diferència del 303) — mateixa font que el Compte de Pèrdues
    i Guanys (`llibres.py::compte_resultats`): comptes 7 (ingressos, ja nets
    d'IVA perquè el 477 és un compte a part) i 6 (despeses, amortització
    inclosa via 681)."""
    fins = _fi_de_mes(year, trimestre * 3)
    saldos = _saldos_per_tipus(
        db, (AccountType.ingres, AccountType.despesa), data_fins=fins, data_des_de=date(year, 1, 1),
    )
    ingressos = sum((l.saldo for l in saldos[AccountType.ingres]), Decimal("0"))
    despeses = sum((l.saldo for l in saldos[AccountType.despesa]), Decimal("0"))
    rendiment_net = ingressos - despeses

    reduccio = Decimal("0.00")
    if aplicar_reduccio_5pct and rendiment_net > 0:
        reduccio = min((rendiment_net * Decimal("0.05")).quantize(Decimal("0.01")), REDUCCIO_5PCT_TOPALL_ANUAL)
    rendiment_net_reduit = rendiment_net - reduccio

    casella_05 = (rendiment_net_reduit * Decimal("0.20")).quantize(Decimal("0.01")) if rendiment_net_reduit > 0 else Decimal("0.00")

    pagaments_anteriors = Decimal("0.00")
    if trimestre > 1:
        anterior = _calcula_130(db, year, trimestre - 1, aplicar_reduccio_5pct)
        pagaments_anteriors = anterior.resultat

    resultat = max(casella_05 - pagaments_anteriors, Decimal("0.00"))

    return Model130Out(
        year=year, trimestre=trimestre,
        casella_01_ingressos_acumulats=ingressos, casella_02_despeses_acumulades=despeses,
        casella_03_rendiment_net=rendiment_net,
        reduccio_5pct_aplicada=aplicar_reduccio_5pct, reduccio_5pct_import=reduccio,
        rendiment_net_reduit=rendiment_net_reduit,
        casella_05_import=casella_05, casella_07_pagaments_anteriors=pagaments_anteriors,
        resultat=resultat,
    )


@router.get("/aeat/130/{year}/{trimestre}", response_model=Model130Out)
def model_130(year: int, trimestre: int, aplicar_reduccio_5pct: bool = False, db: Session = Depends(get_db)):
    """Pagament fraccionat d'IRPF (Autònoms, estimació directa). `aplicar_reduccio_5pct`
    (despeses de difícil justificació, topall 2.000€/any) NOMÉS és correcte
    sota estimació directa SIMPLIFICADA — per defecte no s'aplica."""
    if not (1 <= trimestre <= 4):
        raise HTTPException(422, "Trimestre ha de ser entre 1 i 4")
    out = _calcula_130(db, year, trimestre, aplicar_reduccio_5pct)

    config = db.scalar(select(ConfiguracioBotiga))
    if config and config.legal_form == "sl":
        out.forma_juridica_nota = (
            "Aquest tenant està configurat com a SL: el Model 130 NO li aplica (tributa per "
            "Impost de Societats, models 200/202). Aquest càlcul es mostra igualment com a informació."
        )
    return out


def _nota_autonom(db: Session) -> str | None:
    config = db.scalar(select(ConfiguracioBotiga))
    if config and config.legal_form == "autonom":
        return (
            "Aquest tenant està configurat com a Autònom: l'Impost de Societats (models 200/202) NO li "
            "aplica (tributa per IRPF, models 130/100). Aquest càlcul es mostra igualment com a informació."
        )
    return None


@router.get("/aeat/200/{year}", response_model=Model200Out)
def model_200(
    year: int, tipus_pct: Decimal, pagaments_fraccionats_satisfets: Decimal = Decimal("0.00"),
    db: Session = Depends(get_db),
):
    """Model 200 (Impost de Societats) — ESTIMACIÓ DE SUPORT, no un càlcul
    fiscal complet. `tipus_pct` és sempre obligatori: depèn de fets reals
    del negoci (any de constitució, xifra de negoci) que aquest sistema no
    pot deduir sol — 25% general, 15% entitat de nova creació, o el tipus
    reduït d'empresa de reduïda dimensió, segons toqui. Ver Model200Out per
    a què queda deliberadament fora d'abast (ajustos extracomptables,
    compensació de BINs, deduccions)."""
    saldos = _saldos_per_tipus(
        db, (AccountType.ingres, AccountType.despesa), data_fins=date(year, 12, 31), data_des_de=date(year, 1, 1),
    )
    ingressos = sum((l.saldo for l in saldos[AccountType.ingres]), Decimal("0"))
    despeses = sum((l.saldo for l in saldos[AccountType.despesa]), Decimal("0"))
    resultat_comptable = ingressos - despeses
    base_imposable = resultat_comptable  # ajustos_extracomptables sempre 0, ver docstring del schema

    quota_integra = (
        (base_imposable * tipus_pct / 100).quantize(Decimal("0.01")) if base_imposable > 0 else Decimal("0.00")
    )
    resultat = quota_integra - pagaments_fraccionats_satisfets

    return Model200Out(
        year=year, forma_juridica_nota=_nota_autonom(db),
        resultat_comptable=resultat_comptable, base_imposable=base_imposable,
        tipus_pct=tipus_pct, quota_integra=quota_integra,
        pagaments_fraccionats_satisfets=pagaments_fraccionats_satisfets,
        resultat=resultat,
    )


PERIODES_202 = {1: "Abril", 2: "Octubre", 3: "Desembre"}


@router.get("/aeat/202/{year}/{periode}", response_model=Model202Out)
def model_202(year: int, periode: int, cuota_integra_exercici_anterior: Decimal, db: Session = Depends(get_db)):
    """Model 202 (pagament fraccionat de l'IS), modalitat estàndard art. 40.2
    LIS: 18% de la quota íntegra de l'últim exercici declarat, mateix import
    als 3 períodes. `cuota_integra_exercici_anterior` és sempre un import
    introduït a mà — aquest sistema no guarda Models 200 d'exercicis
    anteriors dels quals derivar-lo."""
    if periode not in PERIODES_202:
        raise HTTPException(422, "Periode ha de ser 1 (abril), 2 (octubre) o 3 (desembre)")
    pct = Decimal("18.00")
    import_pagament = max(
        (cuota_integra_exercici_anterior * pct / 100).quantize(Decimal("0.01")), Decimal("0.00"),
    )
    return Model202Out(
        year=year, periode=periode, periode_nom=PERIODES_202[periode], forma_juridica_nota=_nota_autonom(db),
        cuota_integra_exercici_anterior=cuota_integra_exercici_anterior, pct=pct, import_pagament=import_pagament,
    )
