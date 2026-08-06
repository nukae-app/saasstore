"""Test d'integració de l'alta pública al club del disc: activar el toggle
de configuració, donar-se d'alta triant periodicitat i quantitat (captura
del token COF via Redsys) i verificar tant el camí d'èxit com el de
denegació."""

import base64
import contextlib
import hashlib
import hmac
import io
import json
import re
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.config import get_settings
from app.models import ConfiguracioSubscripcio, EstatCobrament, EstatSubscripcio, Subscripcio, User
from app.services.subscripcions import proxima_facturacio_alta, proxima_facturacio_seguent


def _sign_as_redsys(params: dict) -> tuple[str, str]:
    """Mateixa firma que faria Redsys de veritat (mateix helper que test_tienda.py)."""
    from app.services.redsys import TripleDES
    from cryptography.hazmat.primitives.ciphers import Cipher, modes

    secret_key = get_settings().redsys_secret_key
    key = base64.b64decode(secret_key)
    order_id = params["Ds_Order"]
    data = order_id.encode("utf-8")
    data += b"\x00" * (-len(data) % 8)
    cipher = Cipher(TripleDES(key), modes.CBC(b"\x00" * 8))
    encryptor = cipher.encryptor()
    derived_key = encryptor.update(data) + encryptor.finalize()

    params_b64 = base64.b64encode(json.dumps(params).encode("utf-8")).decode("ascii")
    digest = hmac.new(derived_key, params_b64.encode("ascii"), hashlib.sha256).digest()
    signature = base64.b64encode(digest).decode("ascii").replace("+", "-").replace("/", "_")
    return params_b64, signature


def _login(client, email):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _admin_token(client, db, email="admin@example.com") -> str:
    _login(client, email)
    user = db.scalar(select(User).where(User.email == email))
    user.rol = "admin"
    db.commit()
    return _login(client, email)


def _activar_subscripcions(client, db) -> ConfiguracioSubscripcio:
    admin_access = _admin_token(client, db)
    r = client.patch(
        "/admin/configuracio", json={"subscripcions_actives": True},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert r.status_code == 200 and r.json()["subscripcions_actives"] is True

    config = ConfiguracioSubscripcio(
        id=1, preu_per_disc=Decimal("20.00"),
        periodicitats_mesos_disponibles=[1, 2], quantitats_disponibles=[1, 2, 3],
    )
    db.add(config)
    db.commit()
    return config


def _client_amb_adreca(client, db, email="client@example.com") -> tuple[str, str]:
    access = _login(client, email)
    addr = client.post(
        "/me/addresses",
        json={"nombre_destinatario": "Client", "linea1": "Carrer Fals 1", "ciudad": "Barcelona", "cp": "08001"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert addr.status_code == 201
    return access, addr.json()["id"]


def test_config_amagada_si_el_toggle_esta_desactivat(db, client):
    assert client.get("/subscripcions/config").status_code == 404


def test_alta_valida_periodicitat_i_quantitat_disponibles(db, client):
    _activar_subscripcions(client, db)
    access, address_id = _client_amb_adreca(client, db)

    alta = client.post(
        "/subscripcions/alta",
        json={"periodicitat_mesos": 6, "quantitat": 1, "address_id": address_id},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert alta.status_code == 422


def test_alta_i_notificacio_autoritzada_activa_la_subscripcio(db, client):
    config = _activar_subscripcions(client, db)
    access, address_id = _client_amb_adreca(client, db)

    config_resp = client.get("/subscripcions/config")
    assert config_resp.status_code == 200
    assert config_resp.json()["preu_per_disc"] == "20.00"

    alta = client.post(
        "/subscripcions/alta",
        json={"periodicitat_mesos": 2, "quantitat": 3, "address_id": address_id},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert alta.status_code == 200
    body = alta.json()
    subscripcio_id = uuid.UUID(body["subscripcio_id"])
    merchant_params = json.loads(base64.b64decode(body["Ds_MerchantParameters"]))
    ds_order = merchant_params["DS_MERCHANT_ORDER"]
    # Regressió: si Redsys notifica /checkout/pay/redsys/notify (que busca un
    # Payment, no un CobramentSubscripcio), l'alta es queda "pendent" per
    # sempre encara que el banc autoritzi el cobrament.
    assert merchant_params["DS_MERCHANT_MERCHANTURL"].endswith("/api/subscripcions/pay/redsys/notify")

    db.expire_all()
    subscripcio = db.get(Subscripcio, subscripcio_id)
    assert subscripcio.estat == EstatSubscripcio.pendent_pagament
    assert subscripcio.preu_periode == Decimal("60.00")  # 20.00 * 3
    cicle_1 = proxima_facturacio_alta(date.today())
    assert subscripcio.proxima_facturacio == cicle_1

    params_b64, signature = _sign_as_redsys({
        "Ds_Order": ds_order, "Ds_Response": "0000", "Ds_Merchant_Identifier": "TOKEN-COF-123",
    })
    with contextlib.redirect_stdout(io.StringIO()):
        notify = client.post(
            "/subscripcions/pay/redsys/notify",
            data={"Ds_SignatureVersion": "HMAC_SHA256_V1", "Ds_MerchantParameters": params_b64, "Ds_Signature": signature},
        )
    assert notify.status_code == 200

    db.expire_all()
    subscripcio = db.get(Subscripcio, subscripcio_id)
    assert subscripcio.estat == EstatSubscripcio.activa
    assert subscripcio.redsys_identifier == "TOKEN-COF-123"
    assert subscripcio.proxima_facturacio == proxima_facturacio_seguent(cicle_1, 2)
    assert subscripcio.cobraments[0].estat == EstatCobrament.cobrat
    assert subscripcio.cobraments[0].import_ == Decimal("60.00")
    assert subscripcio.cobraments[0].periode == cicle_1


def test_alta_denegada_descarta_la_subscripcio_pendent(db, client):
    _activar_subscripcions(client, db)
    access, address_id = _client_amb_adreca(client, db, email="denegat@example.com")

    alta = client.post(
        "/subscripcions/alta",
        json={"periodicitat_mesos": 1, "quantitat": 1, "address_id": address_id},
        headers={"Authorization": f"Bearer {access}"},
    )
    body = alta.json()
    subscripcio_id = uuid.UUID(body["subscripcio_id"])
    ds_order = json.loads(base64.b64decode(body["Ds_MerchantParameters"]))["DS_MERCHANT_ORDER"]

    params_b64, signature = _sign_as_redsys({"Ds_Order": ds_order, "Ds_Response": "0180"})
    with contextlib.redirect_stdout(io.StringIO()):
        notify = client.post(
            "/subscripcions/pay/redsys/notify",
            data={"Ds_SignatureVersion": "HMAC_SHA256_V1", "Ds_MerchantParameters": params_b64, "Ds_Signature": signature},
        )
    assert notify.status_code == 200

    db.expire_all()
    assert db.get(Subscripcio, subscripcio_id) is None
