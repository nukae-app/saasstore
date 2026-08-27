"""Els mecanismes que actualitzen el catàleg des de Discogs (botó "Actualitzar
des de Discogs" a l'admin, i l'script sync_discogs_inventory) han de fer
servir el `formato` que ara retorna services.discogs.get_release (abans no
es llegia enlloc, encara que get_release ja el calculés)."""

from decimal import Decimal

import app.services.discogs_sync as discogs_sync
from app.models import Release


def _seed_release(db, **kwargs):
    r = Release(artista="Los Ganglios", title="Peruguay", discogs_release_id=999888, **kwargs)
    db.add(r)
    db.commit()
    return r


def test_enrich_omple_formato_buit(db, monkeypatch):
    release = _seed_release(db, formato=None)

    monkeypatch.setattr(
        discogs_sync, "get_release",
        lambda token, release_id: {"formato": "12\"", "tracklist": [], "credits": []},
    )

    ok = discogs_sync.enrich_release_from_discogs(release, db, "fake-token")
    assert ok is True
    db.refresh(release)
    assert release.formato == '12"'


def test_enrich_no_trepitja_format_ja_omplert_a_ma(db, monkeypatch):
    release = _seed_release(db, formato="EP")

    monkeypatch.setattr(
        discogs_sync, "get_release",
        lambda token, release_id: {"formato": "LP", "tracklist": [], "credits": []},
    )

    discogs_sync.enrich_release_from_discogs(release, db, "fake-token")
    db.refresh(release)
    assert release.formato == "EP"
