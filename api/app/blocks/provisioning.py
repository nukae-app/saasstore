"""Seqüència de blocs amb la qual neix un tenant nou — ver create_tenant()
a routers/superadmin.py. Reprodueix l'ordre i el copy per defecte que
[locale]/page.jsx tenia hardcoded abans del constructor de blocs, perquè un
tenant nou vegi un home complet des del primer dia, no en blanc fins que
algú l'edita a mà. Mateixos valors que la migració de dades
7db26e104bf8_sembrar_home_blocks_per_als_tenants_.py fa servir per als
tenants que ja existien.

Es crida DINS del `with scoped_to(db, tenant.id)` de create_tenant() —
necessita l'autofill de tenant_id (app/tenancy.py), com qualsevol altra
fila sembrada allà (TipusIva, TramEnviament...)."""

from sqlalchemy.orm import Session

from ..models import HomeBlock

HERO_TITLE_RECORDS = "Discos nous i de segona mà."
HERO_SUBTITLE_RECORDS = "Selecció cuidada de vinil, CD i cassette. Comerç de barri des del Poblenou."
HERO_EYEBROW_RECORDS = "Poblenou · Barcelona"
CAROUSEL_PROPS = {
    "heading": "Novetats",
    "subtitle": "Les últimes incorporacions al nostre catàleg.",
    "cta_label": "Veure tot el catàleg",
    "etiqueta_slug": "novetat",
}
CURATOR_SELECTION_PROPS = {"etiqueta_slug": "recomanat"}


def _hero_props(es_records: bool, nombre: str, address: str) -> dict:
    if es_records:
        return {
            "eyebrow": HERO_EYEBROW_RECORDS,
            "title": HERO_TITLE_RECORDS,
            "subtitle": HERO_SUBTITLE_RECORDS,
            "cta_label": "Explorar",
        }
    return {
        "title": nombre or "",
        "subtitle": (address or "").replace("\n", ", "),
        "cta_label": "Explorar",
    }


def provision_default_home_blocks(db: Session, es_records: bool, nombre: str, address: str) -> None:
    blocks = [("hero", _hero_props(es_records, nombre, address)), ("carousel", CAROUSEL_PROPS)]
    if es_records:
        blocks.append(("spotify_recommendations", {}))
    blocks.append(("curator_selection", CURATOR_SELECTION_PROPS))
    if es_records:
        blocks.append(("genre_grid", {}))
    blocks.append(("about_strip", {}))

    for position, (block_type, props) in enumerate(blocks, start=1):
        db.add(HomeBlock(block_type=block_type, props=props, position=position))
