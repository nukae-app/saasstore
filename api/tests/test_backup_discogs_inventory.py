"""Backup de solo lectura del inventario de Discogs (scripts/backup_discogs_inventory.py)."""

import csv
import json

import httpx
import pytest

from app.services import discogs
from scripts import backup_discogs_inventory as backup


def _listing(codi, estat="For Sale"):
    return {
        "id": codi, "status": estat, "price": {"value": 12.5, "currency": "EUR"},
        "release": {"id": 7, "description": "Artista - Títol", "format": "LP", "catalog_number": "X1"},
        "condition": "Mint (M)", "sleeve_condition": "Mint (M)", "comments": "ok", "posted": "2026-01-01",
    }


def test_backup_escribe_json_csv_y_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(discogs, "get_identity", lambda token: "la-botiga")

    def fake_paged(path, token, key, params):
        if params.get("status") == "For Sale":
            return [_listing(1), _listing(2)]
        if params.get("status") == "Draft":
            return [_listing(3, "Draft")]
        raise httpx.HTTPStatusError("400", request=httpx.Request("GET", "http://x"), response=httpx.Response(400))

    monkeypatch.setattr(backup, "_get_paged", fake_paged)
    destino = backup.run("tok", tmp_path)

    assert destino.parent == tmp_path and destino.name.startswith("discogs_la-botiga_")
    assert len(json.loads((destino / "inventory.json").read_text())) == 3
    filas = list(csv.DictReader(open(destino / "inventory.csv", encoding="utf-8")))
    assert [f["listing_id"] for f in filas] == ["1", "2", "3"]
    assert filas[0]["preu"] == "12.5" and filas[0]["descripcio"] == "Artista - Títol"
    manifest = json.loads((destino / "manifest.json").read_text())
    assert manifest["listings_per_estat"] == {"For Sale": 2, "Draft": 1}
    assert set(manifest["estats_fallats"]) == {"Suspended", "Expired"}
    assert not (destino / "orders.json").exists()


def test_backup_falla_si_no_se_puede_leer_for_sale(tmp_path, monkeypatch):
    monkeypatch.setattr(discogs, "get_identity", lambda token: "la-botiga")

    def boom(path, token, key, params):
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(backup, "_get_paged", boom)
    with pytest.raises(httpx.ConnectError):
        backup.run("tok", tmp_path)


def test_backup_orders_opcional(tmp_path, monkeypatch):
    monkeypatch.setattr(discogs, "get_identity", lambda token: "la-botiga")
    monkeypatch.setattr(
        backup, "_get_paged",
        lambda path, token, key, params: [{"id": "1-1"}] if key == "orders" else [_listing(1)],
    )
    destino = backup.run("tok", tmp_path, orders=True)
    assert json.loads((destino / "orders.json").read_text()) == [{"id": "1-1"}]
    assert json.loads((destino / "manifest.json").read_text())["comandes"] == 1


def test_main_exige_token(monkeypatch):
    monkeypatch.delenv("DISCOGS_TOKEN", raising=False)
    monkeypatch.setattr("sys.argv", ["backup"])
    with pytest.raises(SystemExit, match="DISCOGS_TOKEN"):
        backup.main()
