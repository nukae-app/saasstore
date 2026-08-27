"""Verificació de firma HMAC dels webhooks de Revolut Business
(`services/revolut_billing.py`) — pura funció criptogràfica, sense xarxa ni
BD, per poder-la testejar sense credencials reals de Revolut (encara no
n'hi ha, ver models/platform.py per context)."""

import hashlib
import hmac
import time

import pytest

from app.services.revolut_billing import InvalidRevolutSignature, verify_revolut_signature

SECRET = "test-signing-secret"


def _sign(payload: bytes, timestamp: str, secret: str = SECRET) -> str:
    message = f"v1.{timestamp}.".encode() + payload
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return f"v1={digest}"


def test_signatura_valida_passa():
    payload = b'{"event": "SUBSCRIPTION_INITIATED"}'
    timestamp = str(int(time.time() * 1000))
    verify_revolut_signature(payload, _sign(payload, timestamp), timestamp, SECRET)  # no exception


def test_signatura_incorrecta_es_rebutjada():
    payload = b'{"event": "SUBSCRIPTION_INITIATED"}'
    timestamp = str(int(time.time() * 1000))
    with pytest.raises(InvalidRevolutSignature):
        verify_revolut_signature(payload, "v1=deadbeef", timestamp, SECRET)


def test_payload_alterat_es_rebutjat():
    timestamp = str(int(time.time() * 1000))
    signature = _sign(b'{"event": "SUBSCRIPTION_INITIATED"}', timestamp)
    with pytest.raises(InvalidRevolutSignature):
        verify_revolut_signature(b'{"event": "SUBSCRIPTION_CANCELLED"}', signature, timestamp, SECRET)


def test_timestamp_massa_antic_es_rebutjat():
    payload = b'{"event": "SUBSCRIPTION_INITIATED"}'
    old_timestamp = str(int((time.time() - 3600) * 1000))  # fa 1 hora
    with pytest.raises(InvalidRevolutSignature):
        verify_revolut_signature(payload, _sign(payload, old_timestamp), old_timestamp, SECRET)


def test_falten_capcaleres_es_rebutja():
    with pytest.raises(InvalidRevolutSignature):
        verify_revolut_signature(b"{}", None, None, SECRET)


def test_sense_signing_secret_configurat_es_rebutja():
    payload = b'{"event": "SUBSCRIPTION_INITIATED"}'
    timestamp = str(int(time.time() * 1000))
    with pytest.raises(InvalidRevolutSignature):
        verify_revolut_signature(payload, _sign(payload, timestamp), timestamp, "")


def test_multiples_signatures_nomes_cal_que_una_encaixi():
    # Durant una rotació de secret, Revolut pot enviar més d'un token v1=...
    payload = b'{"event": "SUBSCRIPTION_INITIATED"}'
    timestamp = str(int(time.time() * 1000))
    good = _sign(payload, timestamp)
    bad = "v1=0000000000000000000000000000000000000000000000000000000000000000"
    verify_revolut_signature(payload, f"{bad},{good}", timestamp, SECRET)  # no exception
