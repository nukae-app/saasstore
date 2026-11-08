"""Plantillas legales por tenant: se crean las que faltan, no se pisa contenido curado."""

from sqlalchemy import select

from app.models import ConfiguracioBotiga, Pagina, Tenant
from scripts.seed_legal_pages import PAGES, PENDENT, seed


def _tenant_id(db):
    return db.scalar(select(Tenant.id))


BASE = ("avis-legal", "privacitat", "termes", "cookies", "condicions-venda")


def test_crea_les_pagines_en_tres_idiomes_amb_les_dades_del_titular(db):
    out = seed(db, _tenant_id(db))
    db.commit()
    assert len(out) == len(PAGES) == 15
    slugs = {p.slug for p in db.scalars(select(Pagina)).all()}
    # català = slug base (els enllaços de tot el web hi apunten); es/en = sufix d'idioma
    assert slugs == {*BASE, *(f"{s}-es" for s in BASE), *(f"{s}-en" for s in BASE)}
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


def _pagines(db):
    seed(db, _tenant_id(db))
    db.commit()
    return {p.slug: p for p in db.scalars(select(Pagina)).all()}


def test_cap_pagina_te_marcadors_sense_substituir(db):
    for slug, p in _pagines(db).items():
        assert "{nom}" not in p.content and "{email}" not in p.content, slug
        assert "{" not in p.content and "}" not in p.content, slug


def test_les_versions_es_i_en_porten_les_dades_del_titular(db):
    pagines = _pagines(db)
    for lang in ("es", "en"):
        assert "Test Tenant" in pagines[f"avis-legal-{lang}"].content
        assert PENDENT in pagines[f"avis-legal-{lang}"].content  # NIF/email no informats: marcats


def test_enllacos_interns_apunten_a_pagines_existents_amb_prefix_d_idioma(db):
    import re

    pagines = _pagines(db)
    for slug, p in pagines.items():
        lang = slug.rsplit("-", 1)[-1] if slug.endswith(("-es", "-en")) else "ca"
        for href in re.findall(r'href="(/[^"]+)"', p.content):
            m = re.fullmatch(r"/(ca|es|en)/(.+)", href)
            assert m, f"{slug}: enllaç intern sense prefix d'idioma: {href}"
            assert m.group(1) == lang, f"{slug}: enllaç a un altre idioma: {href}"
            destino = m.group(2)
            # pàgines del seed, o rutes de l'app (desistiment és una ruta pròpia, no una Pagina)
            assert destino in {s.removesuffix(f"-{lang}") for s in pagines} or destino == "desistiment", (slug, href)


def test_no_menciona_pasarelas_que_no_son_la_real(db):
    for slug, p in _pagines(db).items():
        assert "Stripe" not in p.content and "Revolut" not in p.content, slug
