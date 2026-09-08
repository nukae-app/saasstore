import uuid
from decimal import Decimal

from pydantic import BaseModel


class Model303TipusOut(BaseModel):
    """Un tram de tipus impositiu — les caselles oficials 01-09 només
    cobreixen 3 trams fixos (general/reduït/superreduït); qualsevol altre
    tipus configurat es reporta a `altres_tipus` de `Model303Out`, no es
    descarta en silenci."""
    pct: Decimal
    base: Decimal
    cuota: Decimal


class Model303Out(BaseModel):
    year: int
    trimestre: int
    mesos: list[int]

    # IVA repercutit — caselles 01-09 (només general 21% / reduït 10% /
    # superreduït 4%, els únics trams amb casella pròpia al model oficial).
    repercutit_general: Model303TipusOut | None = None     # 01/02/03
    repercutit_reduit: Model303TipusOut | None = None      # 04/05/06
    repercutit_superreduit: Model303TipusOut | None = None  # 07/08/09
    altres_tipus_repercutit: list[Model303TipusOut] = []  # trams sense casella pròpia, ver docstring
    casella_27_cuota_meritada: Decimal

    # IVA suportat — desglossat corrents (28/29) vs béns d'inversió (30/31),
    # possible gràcies al source_type de fase 4 (despesa_alta vs actiu_alta).
    casella_28_base_corrent: Decimal
    casella_29_cuota_corrent: Decimal
    casella_30_base_inversio: Decimal
    casella_31_cuota_inversio: Decimal
    casella_45_total_a_deduir: Decimal

    casella_46_resultat_regim_general: Decimal
    casella_64_resultat_liquidacio: Decimal

    # Fora d'abast, informatiu: si n'hi ha, aquest informe no és suficient
    # per si sol i cal revisar-ho amb la gestoria.
    nota_rebu: bool
    fora_abast: list[str] = [
        "Operacions intracomunitàries", "Importacions", "Prorrata", "Compensació de quotes d'exercicis anteriors",
    ]


class Model390TrimestreOut(BaseModel):
    """Una fila del desglossament trimestral dins del resum anual — mateixes
    caselles 27/45/64 que Model303Out, sense repetir el desglossament per tram."""
    trimestre: int
    casella_27_cuota_meritada: Decimal
    casella_45_total_a_deduir: Decimal
    resultat: Decimal


class Model390Out(BaseModel):
    """Resum anual de l'IVA (Model 390) — agrega els 4 trimestres del Model
    303, mateixa font de dades. Mateix abast/limitacions que Model303Out."""
    year: int
    trimestres: list[Model390TrimestreOut]
    casella_27_cuota_meritada_anual: Decimal
    casella_45_total_a_deduir_anual: Decimal
    resultat_anual: Decimal
    nota_rebu: bool
    fora_abast: list[str] = [
        "Operacions intracomunitàries", "Importacions", "Prorrata", "Compensació de quotes d'exercicis anteriors",
        "Volum d'operacions per tipus d'activitat (caselles informatives del model oficial)",
    ]


class Model130Out(BaseModel):
    """Model 130 (pagament fraccionat d'IRPF, Autònoms en estimació directa)
    — NOMÉS té sentit per a `legal_form='autonom'`; una SL tributa per Impost
    de Societats (200/202), no per aquest model (ver `forma_juridica_nota`).

    A diferència del 303 (per trimestre), aquest model és ACUMULAT des de
    l'1 de gener fins al final del trimestre — així ho exigeix el disseny
    oficial (el pagament de cada trimestre es calcula sobre l'acumulat i es
    resta el que ja es va ingressar als trimestres anteriors, casella 07)."""
    year: int
    trimestre: int
    forma_juridica_nota: str | None = None

    casella_01_ingressos_acumulats: Decimal
    casella_02_despeses_acumulades: Decimal
    casella_03_rendiment_net: Decimal

    reduccio_5pct_aplicada: bool
    reduccio_5pct_import: Decimal
    rendiment_net_reduit: Decimal

    casella_04_pct: Decimal = Decimal("20.00")
    casella_05_import: Decimal
    casella_06_retencions_suportades: Decimal = Decimal("0.00")
    casella_07_pagaments_anteriors: Decimal

    resultat: Decimal

    fora_abast: list[str] = [
        "Retencions i ingressos a compte suportats sobre els propis ingressos (casella 06, sempre 0 aquí)",
        "Estimació objectiva (mòduls) — aquest càlcul assumeix estimació directa",
        "Deduccions per maternitat, creació d'ocupació o altres bonificacions",
        "Casella 07 assumeix que els pagaments fraccionats de trimestres anteriors es van ingressar exactament "
        "pel resultat que aquest mateix informe hauria calculat — si es van declarar amb un altre import, cal "
        "ajustar-ho a mà",
    ]


class Model200Out(BaseModel):
    """Model 200 (Impost de Societats, SL) — ESTIMACIÓ DE SUPORT, no un càlcul
    fiscal complet. `tipus_pct` és SEMPRE un paràmetre obligatori (no hi ha
    valor per defecte): depèn de fets reals del negoci (any de constitució,
    xifra de negoci) que aquest sistema no pot deduir — 25% general, 15%
    entitat de nova creació (2 primers exercicis amb base positiva), o el
    tipus reduït d'empresa de reduïda dimensió, segons toqui.

    `ajustos_extracomptables` és sempre 0 aquí: cap ajust (despeses no
    deduïbles, excés d'amortització sobre taules fiscals, compensació de
    bases imposables negatives d'exercicis anteriors...) està modelat. La
    base imposable mostrada és, per tant, EL RESULTAT COMPTABLE SENSE CAP
    AJUST — una simplificació forta, no una xifra fiscal definitiva. NO
    presentar aquest model a Hisenda sense revisar-ho amb la gestoria."""
    year: int
    forma_juridica_nota: str | None = None

    resultat_comptable: Decimal
    ajustos_extracomptables: Decimal = Decimal("0.00")
    base_imposable: Decimal

    tipus_pct: Decimal
    quota_integra: Decimal
    deduccions_bonificacions: Decimal = Decimal("0.00")
    pagaments_fraccionats_satisfets: Decimal
    retencions_i_ingressos_a_compte: Decimal = Decimal("0.00")

    resultat: Decimal

    fora_abast: list[str] = [
        "Ajustos extracomptables (despeses no deduïbles, excés d'amortització sobre taules fiscals, provisions no "
        "deduïbles...) — la base imposable mostrada és el resultat comptable sense cap ajust",
        "Compensació de bases imposables negatives d'exercicis anteriors",
        "Deduccions i bonificacions de la quota (I+D+i, donatius, creació d'ocupació...)",
        "Retencions i ingressos a compte suportats sobre els propis ingressos (sempre 0 aquí)",
        "pagaments_fraccionats_satisfets és un import introduït a mà, no es desa ni es verifica contra cap "
        "Model 202 presentat de veritat",
    ]


class Model202Out(BaseModel):
    """Model 202 (pagament fraccionat de l'Impost de Societats), modalitat
    estàndard art. 40.2 LIS: 18% de la quota íntegra de l'últim exercici
    declarat, mateix import als 3 períodes (abril/octubre/desembre) — NO la
    modalitat opcional art. 40.3 (base del període transcorregut de l'any en
    curs), que aquest informe no cobreix. `cuota_integra_exercici_anterior`
    és sempre un import introduït a mà: aquest sistema no guarda cap Model
    200 d'exercicis anteriors del qual derivar-lo."""
    year: int
    periode: int  # 1=abril, 2=octubre, 3=desembre
    periode_nom: str
    forma_juridica_nota: str | None = None

    cuota_integra_exercici_anterior: Decimal
    pct: Decimal = Decimal("18.00")
    import_pagament: Decimal

    fora_abast: list[str] = [
        "Modalitat opcional art. 40.3 LIS (base del període transcorregut de l'exercici en curs)",
        "Deduccions i bonificacions aplicables al pagament fraccionat",
    ]


class RetencioProveidorOut(BaseModel):
    """Una fila del desglossament per perceptor dels models 111/115."""
    proveidor_id: uuid.UUID | None
    nom: str
    nif: str | None
    base: Decimal
    retencio: Decimal


class ModelRetencioOut(BaseModel):
    """Caselles compartides pels models 111 (retencions a professionals) i 115
    (retenció de lloguer): mateixa estructura oficial (nombre de perceptors,
    base, retenció), només canvia la font (Despesa.retencio_tipus)."""
    year: int
    trimestre: int
    mesos: list[int]
    num_perceptors: int
    base_total: Decimal
    retencio_total: Decimal
    desglossat: list[RetencioProveidorOut]
    fora_abast: list[str] = ["Rendiments del treball (nòmines) — aquest negoci no modela empleats"]


class ModelRetencioTrimestreOut(BaseModel):
    """Una fila del desglossament trimestral dins del resum anual — NOMÉS
    informativa (els totals per trimestre poden sobrecomptar un mateix
    perceptor que apareix en més d'un trimestre); `num_perceptors` de
    `ModelRetencioAnualOut` és el recompte correcte, sobre tot l'any."""
    trimestre: int
    base_total: Decimal
    retencio_total: Decimal


class ModelRetencioAnualOut(BaseModel):
    """Resum anual dels models 111/115: Model 190 (professionals) i Model 180
    (lloguer) — mateix criteri que Model390Out sobre el 303, agrega tot
    l'any en una única consulta perquè un perceptor amb factures en dos
    trimestres compti com UN perceptor, no dos."""
    year: int
    trimestres: list[ModelRetencioTrimestreOut]
    num_perceptors: int
    base_total: Decimal
    retencio_total: Decimal
    desglossat: list[RetencioProveidorOut]
    fora_abast: list[str] = ["Rendiments del treball (nòmines) — aquest negoci no modela empleats"]
