"""Verifica que la consulta de scripts.backfill_formato distingeix "sense
format" i "format brut" (text lliure heretat) de "format ja net" (un dels
7 valors canònics) — sense això, --force reprocessaria tot el catàleg
innecessàriament, i el mode per defecte no netejaria res brut."""

from sqlalchemy import or_, select

from app.models import Release
from app.services.discogs import FORMATS_CANONICS


def _seed(db):
    net = Release(artista="A", titulo="Net", discogs_release_id=1, formato="LP")
    brut = Release(artista="B", titulo="Brut", discogs_release_id=2, formato="LP, Album, Ltd, RSD")
    buit = Release(artista="C", titulo="Buit", discogs_release_id=3, formato=None)
    sense_discogs_id = Release(artista="D", titulo="Sense ID", discogs_release_id=None, formato=None)
    db.add_all([net, brut, buit, sense_discogs_id])
    db.commit()
    return net, brut, buit, sense_discogs_id


def test_query_per_defecte_selecciona_buits_i_bruts_no_els_nets(db):
    net, brut, buit, sense_discogs_id = _seed(db)

    stmt = (
        select(Release)
        .where(Release.discogs_release_id.isnot(None))
        .where(or_(Release.formato.is_(None), Release.formato.notin_(FORMATS_CANONICS)))
    )
    resultat = {r.id for r in db.scalars(stmt)}

    assert resultat == {brut.id, buit.id}
    assert net.id not in resultat
    assert sense_discogs_id.id not in resultat


def test_query_force_selecciona_tots_els_vinculats_a_discogs(db):
    net, brut, buit, sense_discogs_id = _seed(db)

    stmt = select(Release).where(Release.discogs_release_id.isnot(None))
    resultat = {r.id for r in db.scalars(stmt)}

    assert resultat == {net.id, brut.id, buit.id}
    assert sense_discogs_id.id not in resultat
