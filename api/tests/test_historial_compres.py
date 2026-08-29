"""El buscador de proveïdor (/admin/historial-compres) ha de combinar
l'històric importat dels fulls de càlcul (HistorialCompra) amb les comandes
reals fetes des del sistema (Comanda/ComandaLinea), perquè no es quedi
congelat a la importació inicial."""

import contextlib
import io
import re
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select

from app.models import Comanda, ComandaLinea, EstadoComanda, HistorialCompra, Proveedor, Release, Tenant, User


def _login(client, email: str) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _admin_token(client, db) -> str:
    access = _login(client, "admin@example.com")
    user = db.scalar(select(User).where(User.email == "admin@example.com"))
    user.role = "admin"
    db.commit()
    return access


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_proveedor(db, nombre="DistroX") -> Proveedor:
    p = Proveedor(name=nombre)
    db.add(p)
    db.commit()
    return p


def _seed_comanda(db, proveedor, release, status, fecha=None, cantidad=2) -> Comanda:
    c = Comanda(
        proveedor_id=proveedor.id, date=fecha or datetime(2026, 6, 1),
        status=status, order_number=f"2026-{uuid.uuid4().hex[:8]}",
    )
    db.add(c)
    db.flush()
    db.add(ComandaLinea(comanda_id=c.id, release_id=release.id, quantity=cantidad))
    db.commit()
    return c


def test_buscador_troba_comandes_reals_enviades(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = Release(artista="Los Ganglios", title="Peruguay", formato="LP")
    db.add(release)
    db.commit()
    _seed_comanda(db, prov, release, EstadoComanda.enviada)

    resp = client.get("/admin/historial-compres?q=Ganglios", headers=_auth(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["proveedor_nombre"] == "DistroX"
    assert body[0]["artist"] == "Los Ganglios"
    assert body[0]["quantity"] == 2


def test_buscador_exclos_fora_del_vertical_discos(db, client):
    """§17.1: el buscador de proveïdor per artista/segell és un heurístic
    de discos (JOIN directe contra RecordProduct) — per a qualsevol altre
    vertical no ha de calcular res, no intentar-ho i fallar en silenci."""
    tenant = db.get(Tenant, db.info["tenant_id"])
    tenant.vertical_id = "floristry"
    db.commit()

    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = Release(title="Ram de proves")
    db.add(release)
    db.commit()
    _seed_comanda(db, prov, release, EstadoComanda.enviada)
    db.add(HistorialCompra(proveedor_id=prov.id, date=date(2026, 1, 1), release_id=release.id))
    db.commit()

    assert client.get("/admin/historial-compres", headers=_auth(admin)).json() == []
    assert client.get("/admin/historial-compres/resum", headers=_auth(admin)).json() == []


def test_buscador_ignora_esborrany_i_cancelada(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = Release(artista="Second Hand", title="Rarity", formato="LP")
    db.add(release)
    db.commit()
    _seed_comanda(db, prov, release, EstadoComanda.esborrany)
    _seed_comanda(db, prov, release, EstadoComanda.cancelada)

    resp = client.get("/admin/historial-compres?q=Second Hand", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json() == []


def test_buscador_combina_historial_importat_i_comandes_reals(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = Release(artista="Mixed Source", title="Album", formato="LP")
    db.add(release)
    db.commit()

    db.add(HistorialCompra(
        proveedor_id=prov.id, date=date(2020, 1, 1), artist="Mixed Source",
        title="Album (import antic)", quantity=1,
    ))
    db.commit()
    _seed_comanda(db, prov, release, EstadoComanda.rebuda, fecha=datetime(2026, 6, 1))

    resp = client.get("/admin/historial-compres?q=Mixed Source", headers=_auth(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    # La comanda real (2026) és més recent que la de l'històric importat (2020).
    assert body[0]["date"] == "2026-06-01"
    assert body[1]["date"] == "2020-01-01"


def test_resum_suma_comptadors_de_les_dues_fonts(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = Release(artista="Resum Test", title="Album", formato="LP")
    db.add(release)
    db.commit()

    db.add(HistorialCompra(
        proveedor_id=prov.id, date=date(2020, 1, 1), artist="Resum Test", title="Album", quantity=1,
    ))
    db.commit()
    _seed_comanda(db, prov, release, EstadoComanda.enviada, fecha=datetime(2026, 6, 1))

    resp = client.get("/admin/historial-compres/resum?q=Resum Test", headers=_auth(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["proveedor_nombre"] == "DistroX"
    assert body[0]["count"] == 2
    assert body[0]["ultima_compra"] == "2026-06-01"
