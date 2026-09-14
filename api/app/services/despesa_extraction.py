"""Extracció automàtica de dades d'una factura de proveïdor en PDF, per
prellenar l'alta de `Despesa` (veure `routers/comptabilitat/despeses_imports.py`).

Sempre és un ESBORRANY: el resultat es guarda a `DespesaImport.extracted_data`
(JSON) i mai es contabilitza directament — l'usuari revisa/corregeix al
formulari existent de `Despesa` abans de confirmar. Servei aïllat i fàcil de
substituir (p. ex. per extracció basada en regles) sense tocar el router ni
el model, veure CLAUDE.md secció ERP."""

import base64
import json
import logging
import re

import anthropic
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import CategoriaDespesa, Proveedor

log = logging.getLogger(__name__)

MODEL = "claude-sonnet-5"

_CATEGORIES = ", ".join(c.value for c in CategoriaDespesa)

PROMPT = f"""Ets un assistent que llegeix factures de proveïdor d'una botiga de \
discos a Barcelona i n'extreu dades per a comptabilitat. Analitza el PDF adjunt \
i retorna NOMÉS un JSON vàlid (sense markdown, sense explicació) amb aquesta forma:

{{
  "supplier_name": string o null,
  "supplier_nif": string o null (CIF/NIF si apareix),
  "invoice_number": string o null,
  "invoice_date": string "YYYY-MM-DD" o null,
  "taxable_base": number o null (base imposable, sense IVA),
  "vat_pct": number o null (percentatge d'IVA, p.ex. 21),
  "total": number o null (import total de la factura),
  "category": un d'aquests valors exactes o null si no n'estàs segur: {_CATEGORIES},
  "concept": string curt o null (de què tracta la factura),
  "confidence": "alta", "mitjana" o "baixa" segons la teva seguretat global
}}

Si el document no és una factura llegible, retorna tots els camps a null i \
confidence "baixa". No inventis dades que no apareguin al document."""


class ExtractedDespesaData(BaseModel):
    supplier_name: str | None = None
    supplier_nif: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    taxable_base: float | None = None
    vat_pct: float | None = None
    total: float | None = None
    category: str | None = None
    concept: str | None = None
    confidence: str | None = None


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    return match.group(1) if match else text


def _match_proveidor(db: Session, nif: str | None, name: str | None) -> "str | None":
    """Intenta fer coincidir el proveïdor extret amb un ja donat d'alta. NIF
    exacte primer (més fiable); si no, nom per similitud NOMÉS si hi ha un
    únic candidat — un match ambigu és pitjor que cap match."""
    if nif:
        prov = db.scalar(select(Proveedor).where(Proveedor.nif == nif))
        if prov:
            return str(prov.id)
    if name:
        candidats = db.scalars(select(Proveedor).where(Proveedor.name.ilike(f"%{name}%"))).all()
        if len(candidats) == 1:
            return str(candidats[0].id)
    return None


async def extract_despesa_data(pdf_bytes: bytes, db: Session, settings: Settings) -> tuple[dict | None, str | None]:
    """Retorna (extracted_data, error_message) — sempre l'un o l'altre, mai
    els dos. `extracted_data` inclou `proveidor_id` si s'ha pogut fer match."""
    if not settings.anthropic_api_key:
        return None, "No hi ha cap clau de Claude configurada (CLAUDE_KEY_INVOICE)"

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        message = await client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": base64.b64encode(pdf_bytes).decode("ascii"),
                        },
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }],
        )
        raw = message.content[0].text
    except Exception as e:
        log.warning("Claude despesa extraction failed: %s", e)
        return None, f"Error cridant a Claude: {e}"

    try:
        parsed = ExtractedDespesaData.model_validate(json.loads(_strip_json_fences(raw)))
    except (json.JSONDecodeError, ValidationError) as e:
        log.warning("Claude despesa extraction: resposta no vàlida: %s — %r", e, raw[:500])
        return None, "La resposta de Claude no és un JSON vàlid"

    if parsed.category and parsed.category not in {c.value for c in CategoriaDespesa}:
        parsed.category = None

    data = parsed.model_dump()
    data["proveidor_id"] = _match_proveidor(db, parsed.supplier_nif, parsed.supplier_name)
    return data, None
