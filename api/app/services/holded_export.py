"""Connector Holded (API v2) per exportar el llibre diari.

⚠️ MILLOR ESFORÇ, NO VERIFICAT. Es va confirmar per web (developers.holded.com)
que existeixen `POST /api/v2/ledger-entries` (crear assentament) i
`GET /api/v2/accounting-accounts` (llistar pla de comptes), amb autenticació
per header `key: <api_key>` contra `https://api.holded.com`. NO es va poder
confirmar l'esquema exacte del cos JSON (noms de camp de les línies de
debe/haver) — la documentació interactiva no és accessible des d'aquest
entorn i l'OpenAPI spec descarregat no va arribar a la secció de
comptabilitat. El payload de sota és una construcció raonable seguint
convencions habituals d'APIs de comptabilitat (capçalera + array `items`
amb `account`/`debit`/`credit`), NO una confirmació.

Provar contra un compte de prova de Holded (amb una API key real) abans de
confiar-hi amb dades reals. Si el payload no és correcte, Holded hauria de
respondre amb un 4xx que aquest mòdul propaga com `HoldedExportError` amb el
cos de la resposta — no falla en silenci.

No forma part de cap flux automàtic de posting: només s'invoca quan l'admin
prem "Exportar a Holded" (ver routers/comptabilitat/holded.py)."""

import httpx

BASE_URL = "https://api.holded.com/api/v2"


class HoldedExportError(Exception):
    pass


def _client(api_key: str) -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL, headers={"key": api_key, "Content-Type": "application/json"}, timeout=20,
    )


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code >= 400:
        raise HoldedExportError(f"Holded ha respost {resp.status_code}: {resp.text[:500]}")


def list_accounting_accounts(api_key: str) -> list[dict]:
    with _client(api_key) as client:
        resp = client.get("/accounting-accounts")
        _raise_for_status(resp)
        return resp.json()


def push_ledger_entry(api_key: str, *, date_iso: str, description: str, lines: list[dict]) -> dict:
    """`lines`: [{"holded_account_id": str, "debit": Decimal, "credit": Decimal, "description": str|None}, ...]"""
    payload = {
        "date": date_iso,
        "desc": description,
        "items": [
            {
                "account": line["holded_account_id"],
                "debit": float(line["debit"]),
                "credit": float(line["credit"]),
                "desc": line.get("description") or description,
            }
            for line in lines
        ],
    }
    with _client(api_key) as client:
        resp = client.post("/ledger-entries", json=payload)
        _raise_for_status(resp)
        return resp.json()
