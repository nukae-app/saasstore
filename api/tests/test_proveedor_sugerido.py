"""Proveïdor suggerit d'un disc: camp fixat a la fitxa + deducció per l'última compra
(històric importat i comandes reals) + fallback per artista de nom exacte."""

import contextlib
import io
import re
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.models import Comanda, ComandaLinea, EstadoComanda, HistorialCompra, Proveedor, Release, User
from app.routers.erp.solicitudes_compra import _suggest_proveedor_para_release as suggest


def _prov(db, nombre) -> Proveedor:
    p = Proveedor(name=nombre)
    db.add(p)
    db.commit()
    return p


def _release(db, artista, titulo) -> Release:
    r = Release(artista=artista, title=titulo, formato="LP")
    db.add(r)
    db.commit()
    return r


def _historial(db, prov, release=None, fecha=date(2025, 1, 1), artista=None):
    db.add(HistorialCompra(
        proveedor_id=prov.id, date=fecha, release_id=release.id if release else None,
        artist=artista or (release.artista if release else None),
    ))
    db.commit()


def _comanda(db, prov, release, fecha, status=EstadoComanda.rebuda):
    c = Comanda(proveedor_id=prov.id, date=fecha, status=status, order_number=f"2026-{uuid.uuid4().hex[:8]}")
    db.add(c)
    db.flush()
    db.add(ComandaLinea(comanda_id=c.id, release_id=release.id, quantity=1))
    db.commit()


def _nombre(db, release):
    return suggest(db, release.id, release.artista)[1]


def test_una_comanda_real_reciente_gana_a_mucho_historial_antiguo(db):
    """Surprise Chef: 3 compras antiguas a Popstock, pero la última, real, a Universal."""
    popstock, universal = _prov(db, "Popstock"), _prov(db, "Universal")
    r = _release(db, "Surprise Chef", "Frog in a pond")
    for anio in (2023, 2024, 2025):
        _historial(db, popstock, r, date(anio, 5, 1))
    assert _nombre(db, r) == "Popstock"
    _comanda(db, universal, r, datetime(2026, 10, 23, tzinfo=timezone.utc))
    assert _nombre(db, r) == "Universal"


def test_una_comanda_cancelada_o_en_borrador_no_cuenta(db):
    popstock, universal = _prov(db, "Popstock"), _prov(db, "Universal")
    r = _release(db, "Artista", "Disco")
    _historial(db, popstock, r, date(2025, 1, 1))
    _comanda(db, universal, r, datetime(2026, 10, 1, tzinfo=timezone.utc), EstadoComanda.cancelada)
    _comanda(db, universal, r, datetime(2026, 10, 2, tzinfo=timezone.utc), EstadoComanda.esborrany)
    assert _nombre(db, r) == "Popstock"
    _comanda(db, universal, r, datetime(2026, 10, 3, tzinfo=timezone.utc), EstadoComanda.enviada)
    assert _nombre(db, r) == "Universal"


def test_la_mas_reciente_gana_y_el_empate_se_resuelve_por_volumen(db):
    a, b = _prov(db, "A"), _prov(db, "B")
    r = _release(db, "Artista", "Disco")
    _historial(db, a, r, date(2025, 1, 1))
    _historial(db, b, r, date(2026, 1, 1))
    assert _nombre(db, r) == "B"
    # Mismo día: gana quien tiene más compras en total.
    _historial(db, a, r, date(2026, 1, 1))
    _historial(db, a, r, date(2024, 1, 1))
    assert _nombre(db, r) == "A"


def test_el_fallback_por_artista_es_de_nombre_exacto(db):
    """'From' no debe casar con 'Water From Your Eyes'."""
    popstock, granSol = _prov(db, "Popstock"), _prov(db, "Gran Sol")
    otro = _release(db, "Water From Your Eyes", "It's A Beautiful Place")
    _historial(db, popstock, otro, date(2026, 1, 1))
    from_ = _release(db, "From", "Furar Hondo")
    assert suggest(db, from_.id, from_.artista) == (None, None)
    # Otro disco del mismo artista (nombre exacto, sin mayúsculas) sí sirve de pista.
    otro_from = _release(db, "From", "Otro disco")
    _comanda(db, granSol, otro_from, datetime(2026, 6, 1, tzinfo=timezone.utc))
    assert _nombre(db, from_) == "Gran Sol"
    assert suggest(db, from_.id, " FROM ")[1] == "Gran Sol"


def test_el_fallback_por_artista_solo_se_usa_si_el_disco_no_tiene_compras(db):
    a, b = _prov(db, "A"), _prov(db, "B")
    propio = _release(db, "Artista", "Propio")
    hermano = _release(db, "Artista", "Hermano")
    _historial(db, a, propio, date(2020, 1, 1))
    _historial(db, b, hermano, date(2026, 1, 1))
    assert _nombre(db, propio) == "A"


def test_el_proveedor_fijado_en_la_ficha_manda_sobre_todo(db):
    popstock, granSol = _prov(db, "Popstock"), _prov(db, "Gran Sol")
    r = _release(db, "Artista", "Disco")
    _historial(db, popstock, r)
    r.suggested_supplier_id = granSol.id
    db.commit()
    assert suggest(db, r.id, r.artista) == (granSol.id, "Gran Sol")


# --- API: alta/edición del campo desde el catálogo ---------------------------------------

def _admin(client, db) -> dict:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": "admin@example.com"}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    access = client.post(f"/auth/magic-link/verify?token={token}").json()["access_token"]
    db.scalar(select(User).where(User.email == "admin@example.com")).role = "admin"
    db.commit()
    return {"Authorization": f"Bearer {access}"}


def test_fijar_cambiar_y_quitar_el_proveedor_desde_el_catalogo(db, client):
    h = _admin(client, db)
    gran_sol = _prov(db, "Gran Sol")
    created = client.post("/admin/releases", json={"title": "Furar Hondo", "artista": "From"}, headers=h)
    assert created.status_code == 201
    rid = created.json()["id"]

    def fila():
        rows = client.get("/admin/releases", params={"q": "Furar"}, headers=h).json()["releases"]
        return rows[0]

    assert fila()["proveedor_sugerido_id"] is None

    base = {"title": "Furar Hondo", "artista": "From"}
    assert client.put(f"/admin/releases/{rid}", json={**base, "suggested_supplier_id": str(gran_sol.id)}, headers=h).status_code == 200
    assert fila()["proveedor_sugerido_id"] == str(gran_sol.id)
    assert fila()["proveedor_sugerido_nombre"] == "Gran Sol"

    # Un PUT que no menciona el campo (otro cliente) no lo borra.
    assert client.put(f"/admin/releases/{rid}", json={**base, "title": "Furar Hondo (2)"}, headers=h).status_code == 200
    assert fila()["proveedor_sugerido_nombre"] == "Gran Sol"

    # null explícito lo quita.
    assert client.put(f"/admin/releases/{rid}", json={**base, "suggested_supplier_id": None}, headers=h).status_code == 200
    assert fila()["proveedor_sugerido_id"] is None


def test_proveedor_inexistente_se_rechaza_y_no_sale_en_el_catalogo_publico(db, client):
    h = _admin(client, db)
    bad = client.post(
        "/admin/releases", json={"title": "X", "suggested_supplier_id": str(uuid.uuid4())}, headers=h,
    )
    assert bad.status_code == 422
    gran_sol = _prov(db, "Gran Sol")
    rid = client.post(
        "/admin/releases", json={"title": "Y", "suggested_supplier_id": str(gran_sol.id)}, headers=h,
    ).json()["id"]
    detail = client.get(f"/catalog/releases/{rid}")
    # La ficha pública no debe revelar el proveedor.
    assert "suggested_supplier_id" not in detail.text and "Gran Sol" not in detail.text



# --- Endpoint de sugerencia (alta manual) y PATCH del proveedor habitual ------------------

def test_endpoint_proveedor_sugerido_con_y_sin_release(db, client):
    h = _admin(client, db)
    popstock, universal = _prov(db, "Popstock"), _prov(db, "Universal")
    r = _release(db, "Surprise Chef", "Frog in a pond")
    _historial(db, popstock, r, date(2024, 1, 1))
    _comanda(db, universal, r, datetime(2026, 10, 23, tzinfo=timezone.utc))

    url = "/admin/solicitudes-compra/proveedor-sugerido"
    por_release = client.get(url, params={"release_id": str(r.id)}, headers=h).json()
    assert por_release["proveedor_nombre"] == "Universal"
    # Disco aún inexistente: solo se orienta por artista (nombre exacto).
    por_artista = client.get(url, params={"artista": "surprise chef"}, headers=h).json()
    assert por_artista["proveedor_nombre"] == "Universal"
    assert client.get(url, params={"artista": "Surprise"}, headers=h).json() == {"proveedor_id": None, "proveedor_nombre": None}
    assert client.get(url, headers=h).json() == {"proveedor_id": None, "proveedor_nombre": None}


def test_patch_proveedor_sugerido_solo_toca_ese_campo(db, client):
    h = _admin(client, db)
    gran_sol = _prov(db, "Gran Sol")
    r = _release(db, "From", "Furar Hondo")
    url = f"/admin/releases/{r.id}/proveedor-sugerido"

    assert client.patch(url, json={"suggested_supplier_id": str(gran_sol.id)}, headers=h).status_code == 200
    db.refresh(r)
    assert r.suggested_supplier_id == gran_sol.id
    assert (r.artista, r.title, r.formato) == ("From", "Furar Hondo", "LP")  # nada más cambia

    assert client.patch(url, json={"suggested_supplier_id": None}, headers=h).status_code == 200
    db.refresh(r)
    assert r.suggested_supplier_id is None

    assert client.patch(url, json={"suggested_supplier_id": str(uuid.uuid4())}, headers=h).status_code == 422
    assert client.patch(f"/admin/releases/{uuid.uuid4()}/proveedor-sugerido", json={}, headers=h).status_code == 404
