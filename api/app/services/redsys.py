"""Firma de peticiones y verificación de notificaciones de Redsys (TPV Virtual).

Algoritmo oficial (SHA-256 HMAC, versión de firma "HMAC_SHA256_V1"):

1. Se cifra `Ds_Merchant_Order` con 3DES-CBC (IV de ceros) usando la clave
   secreta del comercio como clave 3DES. El resultado es una clave derivada
   distinta para cada pedido.
2. Se firma con HMAC-SHA256 (usando esa clave derivada) el string en base64
   de los parámetros del comercio (`Ds_MerchantParameters`).
3. La firma se manda en base64.

No hay SDK oficial en Python; esto sigue el manual de integración de Redsys.
Las notificaciones (webhook) llegan con la firma en un base64 "url-safe"
(-, _ en vez de +, /), hay que normalizarlo antes de comparar.
"""

import base64
import hashlib
import hmac
import json
import secrets
from decimal import Decimal

import httpx

try:
    from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
except ImportError:  # cryptography < 43
    from cryptography.hazmat.primitives.ciphers.algorithms import TripleDES
from cryptography.hazmat.primitives.ciphers import Cipher, modes

from ..config import get_settings
from ..models import Tenant
from ..tenancy import tenant_frontend_url
from ..tenant_secrets import TenantSecrets

REDSYS_URLS = {
    "test": "https://sis-t.redsys.es:25443/sis/realizarPago",
    "production": "https://sis.redsys.es/sis/realizarPago",
}

# Endpoint REST (trataPeticionREST): mateix TPV, però respon de forma
# SÍNCRONA en el cos de la resposta HTTP (en lloc de notificar per un webhook
# a part). El fem servir per als cobraments recurrents de subscripció
# (`charge_recurring`, transacció MIT: Merchant-Initiated Transaction), on no
# hi ha client ni navegador esperant una redirecció.
REDSYS_WS_URLS = {
    "test": "https://sis-t.redsys.es:25443/sis/rest/trataPeticionREST",
    "production": "https://sis.redsys.es/sis/rest/trataPeticionREST",
}


def _derive_key(order_id: str, secret_key_b64: str) -> bytes:
    key = base64.b64decode(secret_key_b64)
    if len(key) == 16:  # 3DES de 2 claves (EDE2): se expande a 24 bytes
        key += key[:8]
    data = order_id.encode("utf-8")
    data += b"\x00" * (-len(data) % 8)  # relleno a múltiplo de 8, sin padding estándar
    cipher = Cipher(TripleDES(key), modes.CBC(b"\x00" * 8))
    encryptor = cipher.encryptor()
    return encryptor.update(data) + encryptor.finalize()


def _hmac_b64(key: bytes, message: bytes) -> str:
    digest = hmac.new(key, message, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def generate_ds_order() -> str:
    """Ds_Merchant_Order: 4-12 caracteres, los 4 primeros numéricos."""
    return f"{secrets.randbelow(9000) + 1000}{secrets.token_hex(4)}"[:12]


def _urlsafe_to_standard_b64(value: str) -> str:
    return value.replace("-", "+").replace("_", "/")


def _standard_to_urlsafe_b64(value: str) -> str:
    return value.replace("+", "-").replace("/", "_")


def build_payment_form(
    *, ds_order: str, importe: Decimal, order_id_for_url: str, tenant: Tenant, secrets: TenantSecrets,
    environment: str, identifier: str | None = None,
    url_ok: str | None = None, url_ko: str | None = None, notify_url: str | None = None,
) -> dict:
    """Construye los campos del formulario que el frontend debe auto-enviar
    (POST) a la URL de Redsys: Ds_SignatureVersion, Ds_MerchantParameters,
    Ds_Signature, y la propia action URL.

    `identifier="REQUIRED"` (solo en el alta de una subscripción) le pide a
    Redsys que devuelva en la notificación un `Ds_Merchant_Identifier`
    reutilizable, para poder cobrar los períodos siguientes sin repetir el
    formulario (ver `charge_recurring`). Esta primera operación es una CIT
    (Customer-Initiated Transaction: el propio cliente la autoriza con su
    banco en el momento) y se marca como el origen de la credencial guardada
    con `Ds_Merchant_Cof_Ini="S"` + `Ds_Merchant_Cof_Type="R"` (recurrente),
    tal como exige el marco COF de Redsys/PSD2 para que las renovaciones
    posteriores (MIT, ver `charge_recurring`) puedan acogerse a la exención
    de autenticación reforzada.

    `url_ok`/`url_ko`/`notify_url` por defecto se calculan desde el dominio
    del tenant (ver app/tenancy.py::tenant_frontend_url) — antes salían de
    `Settings.frontend_url`/`redsys_notify_url`, globales, incorrectos en
    cuanto hay más de un tenant. El alta de una subscripción (sin `Order` de
    por medio) sigue pasando las suyas propias: su notificación tiene que
    llegar a un endpoint distinto (busca un `CobramentSubscripcio`, no un
    `Payment`) — si no se sobreescribe aquí, Redsys notifica al sitio
    equivocado y el cobro se queda "pendent" para siempre aunque el banco lo
    haya autorizado. `secrets` son las credenciales de ESTE tenant (ver
    app/tenant_secrets.py), nunca compartidas entre tenants."""
    importe_centimos = str(int((importe * 100).to_integral_value()))
    frontend = tenant_frontend_url(tenant)

    merchant_params = {
        "DS_MERCHANT_AMOUNT": importe_centimos,
        "DS_MERCHANT_ORDER": ds_order,
        "DS_MERCHANT_MERCHANTCODE": secrets.redsys_merchant_code,
        "DS_MERCHANT_CURRENCY": "978",  # EUR
        "DS_MERCHANT_TRANSACTIONTYPE": "0",  # autorización estándar
        "DS_MERCHANT_TERMINAL": secrets.redsys_terminal,
        "DS_MERCHANT_MERCHANTURL": notify_url or f"{frontend}/api/checkout/pay/redsys/notify",
        "DS_MERCHANT_URLOK": url_ok or f"{frontend}/checkout/pago-ok?order={order_id_for_url}",
        "DS_MERCHANT_URLKO": url_ko or f"{frontend}/checkout/pago-ko?order={order_id_for_url}",
    }
    if identifier:
        merchant_params["DS_MERCHANT_IDENTIFIER"] = identifier
        merchant_params["DS_MERCHANT_COF_INI"] = "S"
        merchant_params["DS_MERCHANT_COF_TYPE"] = "R"
    params_json = json.dumps(merchant_params)
    params_b64 = base64.b64encode(params_json.encode("utf-8")).decode("ascii")

    derived_key = _derive_key(ds_order, secrets.redsys_secret_key)
    signature = _hmac_b64(derived_key, params_b64.encode("ascii"))

    return {
        "url": REDSYS_URLS[environment],
        "Ds_SignatureVersion": "HMAC_SHA256_V1",
        "Ds_MerchantParameters": params_b64,
        "Ds_Signature": signature,
    }


def extract_ds_order(params_b64: str) -> str | None:
    """Decodifica los parámetros de una notificación SIN verificar la firma
    — solo para saber a qué `Ds_Order` corresponde, y así poder resolver de
    qué tenant es (buscando el `Payment`) ANTES de saber con qué clave
    verificarla. Ver checkout.py::redsys_notify: con la clave ya por tenant,
    no se puede verificar primero y buscar el tenant después (candado
    circular)."""
    try:
        params_json = base64.b64decode(_urlsafe_to_standard_b64(params_b64)).decode("utf-8")
        params = json.loads(params_json)
    except Exception:
        return None
    return params.get("Ds_Order") or params.get("Ds_Merchant_Order")


def verify_signature(params_b64: str, signature_urlsafe: str, secret_key: str) -> dict | None:
    """Verifica la firma de una notificación de Redsys con la clave YA
    conocida (la del tenant al que pertenece, resuelto vía `extract_ds_order`
    + búsqueda del `Payment`). Devuelve el dict de parámetros decodificado
    si la firma es válida, o None si no lo es."""
    params_json = base64.b64decode(_urlsafe_to_standard_b64(params_b64)).decode("utf-8")
    params = json.loads(params_json)
    ds_order = params.get("Ds_Order") or params.get("Ds_Merchant_Order")
    if not ds_order:
        return None

    derived_key = _derive_key(ds_order, secret_key)
    expected = _hmac_b64(derived_key, params_b64.encode("ascii"))
    if not hmac.compare_digest(_standard_to_urlsafe_b64(expected), signature_urlsafe):
        return None
    return params


def charge_recurring(
    *, ds_order: str, importe: Decimal, identifier: str, cof_txnid: str | None = None,
) -> dict | None:
    """Cobrament COF (Credential On File) servidor-a-servidor per a
    renovacions de subscripció: reutilitza l'`identifier` capturat a l'alta
    (veure `build_payment_form(identifier="REQUIRED")`) per cobrar sense
    redirigir ni tornar a mostrar cap formulari al client.

    Aquesta és una transacció MIT (Merchant-Initiated Transaction: la inicia
    el comerç, no el client, que no hi és present). Per PSD2/SCA cal marcar-
    ho explícitament: `Ds_Merchant_DirectPayment="true"`,
    `Ds_Merchant_Excep_Sca="MIT"` (exempció d'autenticació reforçada per
    tractar-se d'una recurrència ja autoritzada pel client a l'alta) i
    `Ds_Merchant_Cof_Ini="N"` (no és la primera operació de la credencial).
    `cof_txnid` és el `Ds_Merchant_Cof_Txnid` que Redsys va retornar a
    l'alta (CIT); és opcional però molt recomanat perquè els esquemes
    (Visa/Mastercard) puguin enllaçar la sèrie de cobraments.

    A diferència de `build_payment_form` (que retorna camps per a un POST-
    redirect del navegador), aquí es crida directament l'endpoint REST de
    Redsys (`REDSYS_WS_URLS`), que respon de forma síncrona amb el mateix
    format que una notificació normal — es reutilitza `verify_signature`
    per validar-la. Retorna `None` si la firma de la resposta no és vàlida.

    NOTA: aquests camps (COF/MIT/SCA) estan documentats per Redsys per a
    "Tokenización" via TPV Virtual + REST; confirma amb el teu banc que el
    contracte concret els té habilitats abans de posar-ho en producció —
    "Paygold" per si sol és un producte diferent (enviar un enllaç de
    pagament per email/SMS que el client obre i paga ell mateix, no un
    cobrament silenciós servidor-a-servidor)."""
    settings = get_settings()
    importe_centimos = str(int((importe * 100).to_integral_value()))

    merchant_params = {
        "DS_MERCHANT_AMOUNT": importe_centimos,
        "DS_MERCHANT_ORDER": ds_order,
        "DS_MERCHANT_MERCHANTCODE": settings.redsys_merchant_code,
        "DS_MERCHANT_CURRENCY": "978",
        "DS_MERCHANT_TRANSACTIONTYPE": "0",
        "DS_MERCHANT_TERMINAL": settings.redsys_terminal,
        "DS_MERCHANT_MERCHANTURL": settings.redsys_notify_url,
        "DS_MERCHANT_IDENTIFIER": identifier,
        "DS_MERCHANT_DIRECTPAYMENT": "true",
        "DS_MERCHANT_EXCEP_SCA": "MIT",
        "DS_MERCHANT_COF_INI": "N",
        "DS_MERCHANT_COF_TYPE": "R",
    }
    if cof_txnid:
        merchant_params["DS_MERCHANT_COF_TXNID"] = cof_txnid
    params_json = json.dumps(merchant_params)
    params_b64 = base64.b64encode(params_json.encode("utf-8")).decode("ascii")

    derived_key = _derive_key(ds_order, settings.redsys_secret_key)
    signature = _hmac_b64(derived_key, params_b64.encode("ascii"))

    response = httpx.post(
        REDSYS_WS_URLS[settings.redsys_environment],
        json={
            "Ds_SignatureVersion": "HMAC_SHA256_V1",
            "Ds_MerchantParameters": params_b64,
            "Ds_Signature": signature,
        },
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    return verify_signature(body["Ds_MerchantParameters"], body["Ds_Signature"], settings.redsys_secret_key)


def is_authorised(ds_response_code: str) -> bool:
    """Códigos 0000-0099 (y 900) son autorizaciones correctas; el resto son
    denegaciones o errores. Ver manual de "Códigos de respuesta" de Redsys."""
    try:
        code = int(ds_response_code)
    except (TypeError, ValueError):
        return False
    return code == 900 or 0 <= code <= 99
