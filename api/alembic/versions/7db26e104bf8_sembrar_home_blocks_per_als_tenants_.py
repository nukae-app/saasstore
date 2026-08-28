"""sembrar home_blocks per als tenants existents

Reprodueix la seqüència fixa que [locale]/page.jsx tenia hardcoded abans
del constructor de blocs (hero, novetats, [spotify], curador, [gèneres],
about) per a cada tenant que ja existeix, AMB el mateix copy per defecte
que es veu avui — sense això, el hero es quedaria sense títol per a tots
els tenants existents, incloent el tenant real en producció.

Per a "records": el mateix copy genèric hardcoded que ja mostra
HomeHero.jsx avui per a tots els tenants d'aquest vertical (no és
específic de cap tenant, ni ho era abans). Per a la resta de verticals:
`nombre`/`address` del propi tenant, que és exactament el que
`isVinils ? ... : config?.nombre/address` triava avui.

Revision ID: 7db26e104bf8
Revises: 42d56e3f1a28
Create Date: 2026-08-28 07:24:00.000000

"""
import json
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '7db26e104bf8'
down_revision: Union[str, None] = '42d56e3f1a28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mateix copy que HomeHero.jsx/page.jsx tenien hardcoded (missatges/ca.json
# home.heroTitle/heroSubtitle/newArrivals/etc.) — es converteix en el valor
# per defecte del bloc en comptes de viure al component.
HERO_TITLE_RECORDS = "Discos nous i de segona mà."
HERO_SUBTITLE_RECORDS = "Selecció cuidada de vinil, CD i cassette. Comerç de barri des del Poblenou."
HERO_EYEBROW_RECORDS = "Poblenou · Barcelona"
CAROUSEL_PROPS = {
    "heading": "Novetats",
    "subtitle": "Les últimes incorporacions al nostre catàleg.",
    "cta_label": "Veure tot el catàleg",
    "etiqueta_slug": "novetat",
}


def _hero_props(es_records: bool, nombre: str, address: str | None) -> dict:
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


def _blocks_for(es_records: bool, nombre: str, address: str | None) -> list[tuple[str, dict]]:
    blocks = [("hero", _hero_props(es_records, nombre, address)), ("carousel", CAROUSEL_PROPS)]
    if es_records:
        blocks.append(("spotify_recommendations", {}))
    blocks.append(("curator_selection", {}))
    if es_records:
        blocks.append(("genre_grid", {}))
    blocks.append(("about_strip", {}))
    return blocks


def upgrade() -> None:
    conn = op.get_bind()
    tenants = conn.execute(
        text(
            """
            SELECT t.id, t.vertical_id, t.nombre, cb.address
            FROM tenants t
            LEFT JOIN configuracio_botiga cb ON cb.tenant_id = t.id
            """
        )
    ).fetchall()
    for tenant_id, vertical_id, nombre, address in tenants:
        blocks = _blocks_for(vertical_id == "records", nombre, address)
        for position, (block_type, props) in enumerate(blocks, start=1):
            conn.execute(
                text(
                    """
                    INSERT INTO home_blocks (tenant_id, block_type, position, enabled, props)
                    VALUES (:tenant_id, :block_type, :position, true, CAST(:props AS json))
                    """
                ),
                {"tenant_id": tenant_id, "block_type": block_type, "position": position, "props": json.dumps(props)},
            )


def downgrade() -> None:
    op.execute("DELETE FROM home_blocks")
