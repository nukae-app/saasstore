"""Fuente única de qué jurisdicciones comptables i formes jurídiques tenen
proveïdor de pla de comptes REAL implementat — mateix criteri que
verticals_registry.py (§20 de docs/ARQUITECTURA_CORE_VERTICAL.md): evita
assignar a un tenant una jurisdicció o forma jurídica sense codi real
darrere."""

# Jurisdiccions amb proveïdor de pla de comptes real implementat
# (services/comptabilitat_seed.py::CHART_PROVIDERS). Afegir-ne una de nova
# és treball de desenvolupament (escriure el seu `seed_pgc_xx`), no de
# configuració des de superadmin.
ACCOUNTING_JURISDICTIONS_IMPLEMENTED: list[str] = ["es"]

# Sembrades a `accounting_jurisdictions` per reservar id/nom des de
# superadmin (amb `active=False`), sense proveïdor real encara: no
# seleccionables en crear un tenant fins que existeixi el seu chart provider.
ACCOUNTING_JURISDICTIONS_PLANNED: list[str] = ["fr", "it", "uk", "us"]

# Formes jurídiques vàlides per jurisdicció — no és text lliure: només les
# que el proveïdor d'aquella jurisdicció sap sembrar. Validat a l'endpoint
# (POST /superadmin/tenants, PATCH /admin/configuracio), no amb un Enum de BD.
LEGAL_FORMS_BY_JURISDICTION: dict[str, list[str]] = {
    "es": ["sl", "autonom"],
    "fr": ["sarl", "ei"],
    "it": ["srl", "ditta_individuale"],
    "uk": ["ltd", "sole_trader"],
    "us": ["llc", "corporation", "sole_proprietor"],
}
