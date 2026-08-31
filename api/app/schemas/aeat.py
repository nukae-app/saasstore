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
