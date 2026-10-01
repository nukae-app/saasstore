"""Salvaguardes de la primera ejecución "Discogs manda" de
scripts/sync_discogs_inventory.py: informe CSV por ítem, freno de seguridad
y marca de adopción hecha. Ver docs/PLAN_CANAL_DISCOGS.md §8."""

import argparse
import csv
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Item, ItemStatus, Release, Tenant
from app.services import discogs_inventory_sync as svc
from app.services.discogs_sync import adopcio_feta
from app.tenant_secrets import TenantSecrets
from scripts import sync_discogs_inventory as script


def _args(tmp_path, **kw) -> argparse.Namespace:
    base = dict(
        tenant="test-tenant", dry_run=False, limit=0, informe=str(tmp_path / "informe.csv"),
        max_retire_pct=20.0, force=False, reobrir_adopcio=False,
    )
    base.update(kw)
    return argparse.Namespace(**base)


def _listing(codi, precio="10.00", release_id=None):
    return {
        "id": codi, "price": {"value": precio},
        "release": {"id": release_id or codi, "description": "Artista - Títol"},
        "condition": "Very Good Plus (VG+)", "sleeve_condition": "VG+", "posted": None,
    }


@pytest.fixture
def discogs(monkeypatch):
    """Falsea la red: devuelve el inventario que fije el test."""
    state = {"listings": []}
    monkeypatch.setattr(svc, "get_tenant_secrets", lambda tid: TenantSecrets(discogs_token="tok"))
    monkeypatch.setattr(svc, "_fetch_username", lambda token: "la-botiga")
    monkeypatch.setattr(svc, "_fetch_inventory", lambda token, user, limit=0, on_page=None: state["listings"][:limit] if limit else state["listings"])
    return state


def _seed(db, n, precio="10.00", codi0=1000):
    """n ejemplares segona_ma disponibles, cada uno con su codi_discogs."""
    items = []
    for k in range(n):
        r = Release(artista=f"A{k}", title=f"T{k}", formato="LP", discogs_release_id=500 + k)
        db.add(r)
        db.flush()
        it = Item(release_id=r.id, price=Decimal(precio), codi_discogs=codi0 + k)
        db.add(it)
        items.append(it)
    db.commit()
    return items


def _tenant(db) -> Tenant:
    return db.scalar(select(Tenant))


def _csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_cero_listings_aborta_en_ejecucion_real(db, discogs, tmp_path):
    items = _seed(db, 3)
    with pytest.raises(SystemExit, match="cap listing"):
        script._run(db, _tenant(db), _args(tmp_path))
    db.expire_all()
    assert all(i.status == ItemStatus.disponible for i in items)
    assert adopcio_feta(db) is None


def test_cero_listings_en_dry_run_avisa_y_genera_informe(db, discogs, tmp_path, capsys):
    items = _seed(db, 3)
    script._run(db, _tenant(db), _args(tmp_path, dry_run=True))
    assert "AVÍS" in capsys.readouterr().out
    filas = _csv(tmp_path / "informe.csv")
    assert [f["accio"] for f in filas] == ["retirar"] * 3
    db.expire_all()
    assert all(i.status == ItemStatus.disponible for i in items)  # dry-run no guarda


def test_freno_por_porcentaje_de_retiradas(db, discogs, tmp_path):
    items = _seed(db, 10)
    discogs["listings"] = [_listing(1000)]  # solo 1 de 10 sigue en Discogs -> 90 % a retirar
    with pytest.raises(SystemExit, match="retirar"):
        script._run(db, _tenant(db), _args(tmp_path))
    db.expire_all()
    assert all(i.status == ItemStatus.disponible for i in items)


def test_force_salta_el_freno_y_retira(db, discogs, tmp_path):
    items = _seed(db, 10)
    discogs["listings"] = [_listing(1000)]
    script._run(db, _tenant(db), _args(tmp_path, force=True))
    db.expire_all()
    assert sum(i.status == ItemStatus.retirado for i in items) == 9


def test_limit_no_retira_nada_ni_marca_adopcion(db, discogs, tmp_path):
    items = _seed(db, 5)
    discogs["listings"] = [_listing(1000 + k) for k in range(5)]
    script._run(db, _tenant(db), _args(tmp_path, limit=2))
    db.expire_all()
    assert all(i.status == ItemStatus.disponible for i in items)
    assert adopcio_feta(db) is None


def test_ejecucion_real_correcta_marca_adopcion_y_bloquea_la_siguiente(db, discogs, tmp_path):
    _seed(db, 5)
    discogs["listings"] = [_listing(1000 + k, precio="12.00" if k == 0 else "10.00") for k in range(5)]

    script._run(db, _tenant(db), _args(tmp_path))
    db.expire_all()
    marca = adopcio_feta(db)
    assert marca is not None and marca["actualitzats"] == 1 and marca["compte_discogs"] == "la-botiga"
    filas = _csv(tmp_path / "informe.csv")
    assert [(f["accio"], f["preu_app"], f["preu_discogs"]) for f in filas] == [("actualitzar_preu", "10.00", "12.00")]

    with pytest.raises(SystemExit, match="adopció"):
        script._run(db, _tenant(db), _args(tmp_path))
    script._run(db, _tenant(db), _args(tmp_path, reobrir_adopcio=True))  # explícito: permitido


def test_dry_run_con_adopcion_hecha_solo_avisa(db, discogs, tmp_path, capsys):
    _seed(db, 2)
    discogs["listings"] = [_listing(1000), _listing(1001)]
    script._run(db, _tenant(db), _args(tmp_path))
    capsys.readouterr()
    script._run(db, _tenant(db), _args(tmp_path, dry_run=True))
    assert "ja consta com a feta" in capsys.readouterr().out


def test_informe_incluye_crear_y_errores_y_con_errores_no_marca(db, discogs, tmp_path, monkeypatch):
    _seed(db, 1)
    nuevo = Release(artista="Nou", title="Disc", formato="LP", discogs_release_id=777)
    db.add(nuevo)
    db.commit()
    monkeypatch.setattr(svc, "_find_or_create_release", lambda db_, token, rid, desc: db_.get(Release, nuevo.id))
    sin_precio = _listing(2000)
    sin_precio["price"] = {}
    discogs["listings"] = [_listing(1000), _listing(3000, release_id=777), sin_precio]

    script._run(db, _tenant(db), _args(tmp_path))
    filas = {f["codi_discogs"]: f for f in _csv(tmp_path / "informe.csv")}
    assert filas["3000"]["accio"] == "crear" and filas["3000"]["artista"] == "Nou"
    assert filas["2000"]["accio"] == "error"
    db.expire_all()
    assert adopcio_feta(db) is None  # hay errores: no se marca
