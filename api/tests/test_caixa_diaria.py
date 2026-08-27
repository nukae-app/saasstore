"""Tests del full de caixa diària manual (control de caja per mètode de pagament / IVA)."""

import calendar
import contextlib
import io
import re
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.models import CanalVenta, MetodoPago, Order, OrderItem, OrderStatus, User, VentaExterna


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


def test_get_caixa_diaria_buida_retorna_tots_els_dies_a_zero(client, db):
    admin = _admin_token(client, db)
    r = client.get("/admin/caixa-diaria/2026/2", headers=_auth(admin))
    assert r.status_code == 200
    data = r.json()
    assert len(data["dies"]) == calendar.monthrange(2026, 2)[1] == 28
    assert data["total_mes"] == "0.00" or float(data["total_mes"]) == 0
    assert data["periode_tancat"] is False


def test_save_i_recuperar_caixa_diaria(client, db):
    admin = _admin_token(client, db)
    payload = [
        {"date": "2026-01-01", "card_21": "100.50", "cash_4": "20"},
        {"date": "2026-01-02", "bizum_21": "30", "cultural_voucher": "15.25"},
    ]
    r = client.put("/admin/caixa-diaria/2026/1", json=payload, headers=_auth(admin))
    assert r.status_code == 200
    data = r.json()
    dia1 = next(d for d in data["dies"] if d["date"] == "2026-01-01")
    assert float(dia1["total_dia"]) == 120.50
    dia2 = next(d for d in data["dies"] if d["date"] == "2026-01-02")
    assert float(dia2["total_dia"]) == 45.25
    assert float(data["total_mes"]) == 165.75

    # Re-fetch to confirm it's persisted, not just echoed
    r2 = client.get("/admin/caixa-diaria/2026/1", headers=_auth(admin))
    assert float(r2.json()["total_mes"]) == 165.75


def test_save_dia_fora_del_mes_rebutjat(client, db):
    admin = _admin_token(client, db)
    payload = [{"date": "2026-02-01", "card_21": "10"}]
    r = client.put("/admin/caixa-diaria/2026/1", json=payload, headers=_auth(admin))
    assert r.status_code == 422


def test_save_amb_periode_tancat_rebutjat(client, db):
    admin = _admin_token(client, db)
    assert client.post("/admin/periodes/2026/1/tancar", headers=_auth(admin)).status_code == 200
    r = client.put(
        "/admin/caixa-diaria/2026/1", json=[{"date": "2026-01-05", "card_21": "10"}], headers=_auth(admin)
    )
    assert r.status_code == 409


def test_export_excel_i_pdf(client, db):
    admin = _admin_token(client, db)
    client.put(
        "/admin/caixa-diaria/2026/3",
        json=[{"date": "2026-03-01", "card_21": "50"}],
        headers=_auth(admin),
    )
    r_xlsx = client.get("/admin/caixa-diaria/2026/3/excel", headers=_auth(admin))
    assert r_xlsx.status_code == 200
    assert r_xlsx.headers["content-type"].startswith("application/vnd.openxmlformats")

    r_pdf = client.get("/admin/caixa-diaria/2026/3/pdf", headers=_auth(admin))
    assert r_pdf.status_code == 200
    assert r_pdf.headers["content-type"] == "application/pdf"


def test_requereix_admin(client, db):
    user_token = _login(client, "user@example.com")
    r = client.get("/admin/caixa-diaria/2026/1", headers=_auth(user_token))
    assert r.status_code == 403


def test_vendes_reals_combina_web_i_tpv_per_iva(client, db):
    admin = _admin_token(client, db)

    # Venda web pagada amb Redsys (targeta), IVA 21%
    order = Order(
        status=OrderStatus.pagado, contact_email="client@example.com",
        total=Decimal("100.00"), shipping_method="envio",
        created_at=datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc),
    )
    db.add(order)
    db.commit()
    db.add(OrderItem(order_id=order.id, price=Decimal("100.00"), vat_pct=Decimal("21.00")))
    db.commit()

    # Venda TPV mostrador en efectiu, IVA 4% (p.ex. un llibre)
    db.add(VentaExterna(
        description="Llibre", channel=CanalVenta.mostrador, payment_method=MetodoPago.efectivo,
        sale_price=Decimal("15.00"), date=datetime(2026, 4, 5, 17, 0, tzinfo=timezone.utc),
        vat_pct=Decimal("4.00"),
    ))
    # Venda TPV mostrador amb targeta, IVA 21%, un altre dia
    db.add(VentaExterna(
        description="Vinil solt", channel=CanalVenta.mostrador, payment_method=MetodoPago.tarjeta,
        sale_price=Decimal("30.00"), date=datetime(2026, 4, 6, 11, 0, tzinfo=timezone.utc),
        vat_pct=Decimal("21.00"),
    ))
    # Venda a Discogs: NO ha d'entrar (no és caixa pròpia)
    db.add(VentaExterna(
        description="Vinil Discogs", channel=CanalVenta.discogs, payment_method=MetodoPago.tarjeta,
        sale_price=Decimal("999.00"), date=datetime(2026, 4, 6, 11, 0, tzinfo=timezone.utc),
        vat_pct=Decimal("21.00"),
    ))
    # Comanda web "paga en recollir": NO ha d'entrar (mètode real no es coneix)
    order_tienda = Order(
        status=OrderStatus.pagado, contact_email="pickup@example.com",
        total=Decimal("500.00"), shipping_method="recogida_tienda", payment_method="tienda",
        created_at=datetime(2026, 4, 6, 11, 0, tzinfo=timezone.utc),
    )
    db.add(order_tienda)
    db.commit()
    db.add(OrderItem(order_id=order_tienda.id, price=Decimal("500.00"), vat_pct=Decimal("21.00")))
    db.commit()

    r = client.get("/admin/caixa-diaria/2026/4/vendes-reals", headers=_auth(admin))
    assert r.status_code == 200
    dies = {d["date"]: d for d in r.json()}

    assert float(dies["2026-04-05"]["card_21"]) == 100.00
    assert float(dies["2026-04-05"]["cash_4"]) == 15.00

    assert float(dies["2026-04-06"]["card_21"]) == 30.00
    # ni el Discogs ni el "tienda" (500) hi apareixen
    assert dies["2026-04-06"]["card_21"] != "999.00"


def test_vendes_reals_inclou_bizum_i_bono_cultural(client, db):
    admin = _admin_token(client, db)

    db.add(VentaExterna(
        description="Vinil Bizum", channel=CanalVenta.mostrador, payment_method=MetodoPago.bizum,
        sale_price=Decimal("25.00"), date=datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc),
        vat_pct=Decimal("21.00"),
    ))
    db.add(VentaExterna(
        description="Llibre Bizum", channel=CanalVenta.mostrador, payment_method=MetodoPago.bizum,
        sale_price=Decimal("9.00"), date=datetime(2026, 5, 3, 12, 30, tzinfo=timezone.utc),
        vat_pct=Decimal("4.00"),
    ))
    # Bono cultural: no es desglossa per IVA, una sola columna
    db.add(VentaExterna(
        description="Vinil bono cultural", channel=CanalVenta.mostrador, payment_method=MetodoPago.bono_cultural,
        sale_price=Decimal("20.00"), date=datetime(2026, 5, 3, 13, 0, tzinfo=timezone.utc),
        vat_pct=Decimal("21.00"),
    ))
    db.commit()

    r = client.get("/admin/caixa-diaria/2026/5/vendes-reals", headers=_auth(admin))
    assert r.status_code == 200
    dia = next(d for d in r.json() if d["date"] == "2026-05-03")

    assert float(dia["bizum_21"]) == 25.00
    assert float(dia["bizum_4"]) == 9.00
    assert float(dia["cultural_voucher"]) == 20.00


def test_ventaexterna_accepta_bizum_i_bono_cultural(client, db):
    from app.models import TipusIva

    admin = _admin_token(client, db)
    tipus = TipusIva(name="General", percentage=Decimal("21.00"), active=True)
    db.add(tipus)
    db.commit()

    for metode in ("bizum", "bono_cultural"):
        r = client.post(
            "/admin/ventas-externas",
            json={
                "description": f"Article {metode}", "tipus_iva_id": tipus.id,
                "channel": "mostrador", "payment_method": metode,
                "sale_price": "10.00", "date": "2026-05-10T10:00:00Z",
            },
            headers=_auth(admin),
        )
        assert r.status_code == 201, r.text
        assert r.json()["payment_method"] == metode
