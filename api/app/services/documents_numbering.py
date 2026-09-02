"""Numeració correlativa per a documents comercials (pressupostos, albarans
i, en el futur, factura de venda — Bloc B2 del pla de paritat amb Holded).

Mateix criteri d'atomicitat que
`services/comptabilitat_posting.py::next_entry_number` (UPDATE condicionat,
mai SELECT+UPDATE): un número duplicat o amb buits és un problema de negoci,
no només un bug. Una sola funció genèrica sobre `DocumentCounter`
(`document_type`) en lloc d'un comptador per tipus."""

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import DocumentCounter


def next_document_number(db: Session, document_type: str, fiscal_year: int) -> int:
    result = db.execute(
        update(DocumentCounter)
        .where(DocumentCounter.document_type == document_type, DocumentCounter.fiscal_year == fiscal_year)
        .values(next_number=DocumentCounter.next_number + 1)
        .returning(DocumentCounter.next_number)
        .execution_options(synchronize_session=False)
    )
    row = result.first()
    if row is not None:
        return row[0] - 1

    try:
        with db.begin_nested():
            db.add(DocumentCounter(document_type=document_type, fiscal_year=fiscal_year, next_number=2))
            db.flush()
        return 1
    except IntegrityError:
        result = db.execute(
            update(DocumentCounter)
            .where(DocumentCounter.document_type == document_type, DocumentCounter.fiscal_year == fiscal_year)
            .values(next_number=DocumentCounter.next_number + 1)
            .returning(DocumentCounter.next_number)
            .execution_options(synchronize_session=False)
        )
        return result.scalar_one() - 1
