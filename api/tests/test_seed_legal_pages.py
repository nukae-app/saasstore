"""Plantillas legales por tenant: se crean las que faltan, no se pisa contenido curado."""

from sqlalchemy import select

from app.models import ConfiguracioBotiga, Pagina, Tenant
from scripts.seed_legal_pages import PAGES, PENDENT, seed


def _tenant_id(db):
    return db.scalar(select(Tenant.id))


def test_crea_les_cinc_pagines_amb_les_dades_del_titular(db):
    out = seed(db, _tenant_id(db))
    db.commit()
    assert len(out) == len(PAGES) == 5
    slugs = {p.slug for p in db.scalars(select(Pagina)).all()}
    assert slugs == {"avis-legal", "privacitat", "termes", "cookies", "condicions-venda"}
    avis = db.scalar(select(Pagina).where(Pagina.slug == "avis-legal"))
    assert "Test Tenant" in avis.content          # fiscal_name de la config de prueba
    assert PENDENT in avis.content                # NIF/email no informados: marcados, no inventados


def test_no_pisa_pagines_existents_sense_overwrite(db):
    db.add(Pagina(slug="privacitat", name="Curada", type="estatica", content="TEXT A MÀ"))
    db.commit()
    seed(db, _tenant_id(db))
    db.commit()
    assert db.scalar(select(Pagina).where(Pagina.slug == "privacitat")).content == "TEXT A MÀ"

    seed(db, _tenant_id(db), overwrite=True)
    db.commit()
    assert "TEXT A MÀ" not in db.scalar(select(Pagina).where(Pagina.slug == "privacitat")).content


def test_escapa_el_html_de_les_dades_del_titular(db):
    cfg = db.scalar(select(ConfiguracioBotiga))
    cfg.fiscal_name = "<script>x</script> SL"
    db.commit()
    seed(db, _tenant_id(db))
    db.commit()
    assert "<script>" not in db.scalar(select(Pagina).where(Pagina.slug == "avis-legal")).content
