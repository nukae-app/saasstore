"""Conciliació bancària automàtica i suggeriments (Bloc B3, veure
docs/PLAN_PARIDAD_HOLDED.md). Coincidència per import EXACTE — un extracte
bancari i una factura haurien de quadrar exactament; no s'aplica cap
tolerància que pugui conciliar per error un moviment amb la despesa
equivocada. Només afecta despeses (moviments de sortida): ingressos (Order/
VentaExterna) no tenen patró recurrent fiable amb el que fer regles."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Despesa, EstatConciliacio, EstatPagamentDespesa, MovimentBancari, ReglaConciliacio
from .comptabilitat_posting import post_despesa_pagament


def find_matching_rule(db: Session, concept: str) -> ReglaConciliacio | None:
    """Primera regla activa el `pattern` de la qual apareix (substring,
    sense distingir majúscules) al concepte del moviment."""
    concept_lower = concept.lower()
    reglas = db.scalars(select(ReglaConciliacio).where(ReglaConciliacio.active == True)).all()
    for regla in reglas:
        if regla.pattern.lower() in concept_lower:
            return regla
    return None


def rank_despesa_candidates(
    db: Session, moviment: MovimentBancari, proveidor_id=None, limit: int = 5,
) -> list[Despesa]:
    """Despeses pendents amb import EXACTE al moviment (abs), ordenades per
    proximitat de data (venciment si n'hi ha, si no data de factura) al
    moviment — servei compartit pels suggeriments manuals i per l'aplicació
    automàtica de regles."""
    import_moviment = abs(moviment.movement_amount)
    stmt = select(Despesa).where(
        Despesa.payment_status != EstatPagamentDespesa.pagat,
        Despesa.total == import_moviment,
    )
    if proveidor_id:
        stmt = stmt.where(Despesa.proveidor_id == proveidor_id)
    candidates = db.scalars(stmt).all()

    def _dies(d: Despesa) -> int:
        referencia = d.due_date or d.invoice_date
        return abs((referencia - moviment.operation_date).days)

    return sorted(candidates, key=_dies)[:limit]


def apply_rules_to_pending(db: Session, compte_id: int) -> int:
    """Aplica les regles actives als moviments de sortida pendents d'aquest
    compte: si el concepte fa match amb una regla i hi ha EXACTAMENT UNA
    despesa candidata (import exacte) del proveïdor de la regla, es concilia
    automàticament — mateixa lògica que la conciliació manual
    (routers/comptabilitat/banc.py::conciliar_moviment). Amb ambigüitat
    (0 o >1 candidates) no es tria res sol, es deixa pendent per a revisió
    manual. Retorna el nombre de moviments conciliats."""
    pendents = db.scalars(
        select(MovimentBancari).where(
            MovimentBancari.compte_id == compte_id,
            MovimentBancari.status == EstatConciliacio.pendent,
            MovimentBancari.movement_amount < 0,
        )
    ).all()

    conciliats = 0
    for mov in pendents:
        regla = find_matching_rule(db, mov.concept)
        if regla is None:
            continue
        candidats = rank_despesa_candidates(db, mov, proveidor_id=regla.proveidor_id, limit=2)
        if len(candidats) != 1:
            continue
        despesa = candidats[0]

        mov.status = EstatConciliacio.conciliat
        mov.despesa_id = despesa.id
        mov.reconciliation_notes = f'Conciliat automàticament per regla "{regla.pattern}"'
        despesa.payment_status = EstatPagamentDespesa.pagat
        despesa.payment_date = mov.operation_date
        post_despesa_pagament(
            db, despesa, payment_date=mov.operation_date, amount=abs(mov.movement_amount), cash=False,
        )
        conciliats += 1

    return conciliats
