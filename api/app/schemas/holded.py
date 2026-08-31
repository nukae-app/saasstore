from pydantic import BaseModel


class HoldedExportIn(BaseModel):
    """`account_mapping`: codi PGC intern -> id de compte a Holded (p. ex.
    {"570": "64f...", "700": "64f..."}). No es persisteix — es passa cada
    vegada que es fa l'exportació, perquè el connector és experimental (ver
    services/holded_export.py) i encara no val la pena una taula pròpia per
    a una correspondència sense verificar contra un compte real."""
    year: int
    mes_desde: int = 1
    mes_fins: int = 12
    account_mapping: dict[str, str]


class HoldedExportLiniaOut(BaseModel):
    entry_number: int
    status: str  # "ok" | "error"
    detail: str | None = None


class HoldedExportOut(BaseModel):
    year: int
    mes_desde: int
    mes_fins: int
    resultats: list[HoldedExportLiniaOut]
