"""Verificació de webhooks de Revolut Business (facturació de plataforma
ALS tenants — no confondre amb `tenant_secrets.py`, que és Redsys/Discogs/
Spotify de cada tenant). NO és un client de l'API de Revolut: les crides de
sortida (crear customer/plan/subscription) encara no s'han construït perquè
no hi ha credencials de sandbox per provar-les — decisió explícita de
l'usuari, 2026-08-27 (veure `models/platform.py` per al context complet).
Aquest mòdul és l'única peça del flux de facturació que SÍ es pot verificar
sense credencials reals: la firma HMAC segueix un esquema publicat.

Esquema assumit a partir de la documentació pública de Revolut (secció
"Verify the payload signature" del Merchant API), NO verificat encara
contra un event real perquè les pàgines de detall bloquegen l'accés
automatitzat — revisar en quant hi hagi accés a sandbox:
- Capçalera `Revolut-Signature`: un o més tokens `v1=<hex hmac-sha256>`
  separats per coma (durant rotació de secret n'hi pot haver més d'un;
  n'hi ha prou que UN encaixi).
- Capçalera `Revolut-Request-Timestamp`: epoch en mil·lisegons, tolerància
  de 5 minuts per mitigar atacs de repetició.
- Missatge signat: "v1.<timestamp>.<payload>" sobre els bytes crus del
  body (abans de parsejar JSON).
"""

import hashlib
import hmac
import time

TIMESTAMP_TOLERANCE_SECONDS = 300


class InvalidRevolutSignature(Exception):
    """El payload no porta una firma vàlida — no s'ha de processar."""


def verify_revolut_signature(
    payload: bytes, signature_header: str | None, timestamp_header: str | None, signing_secret: str,
) -> None:
    """Lança `InvalidRevolutSignature` si el payload no està firmat
    correctament. Pura funció criptogràfica (sense xarxa ni BD) perquè es
    pugui testejar sense credencials reals de Revolut."""
    if not signing_secret:
        raise InvalidRevolutSignature("Cap signing secret configurat")
    if not signature_header or not timestamp_header:
        raise InvalidRevolutSignature("Falten capçaleres de signatura")

    try:
        timestamp_ms = int(timestamp_header)
    except ValueError:
        raise InvalidRevolutSignature("Timestamp invàlid")
    age_seconds = abs(time.time() - timestamp_ms / 1000)
    if age_seconds > TIMESTAMP_TOLERANCE_SECONDS:
        raise InvalidRevolutSignature("Timestamp fora de tolerància (possible repetició)")

    signed_message = f"v1.{timestamp_header}.".encode() + payload
    expected = hmac.new(signing_secret.encode(), signed_message, hashlib.sha256).hexdigest()

    candidates = [
        token.strip()[len("v1="):] for token in signature_header.split(",")
        if token.strip().startswith("v1=")
    ]
    if not candidates or not any(hmac.compare_digest(expected, candidate) for candidate in candidates):
        raise InvalidRevolutSignature("La signatura no coincideix")
