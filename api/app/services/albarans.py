"""Creació de l'albarà d'una comanda — extret perquè el necessiten dos
llocs: l'alta manual (routers/documents/albarans.py) i l'automàtica en
marcar una comanda com a 'enviado' (routers/admin/orders.py)."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Albara, Order
from .documents_numbering import next_document_number


def crear_albara_per_order(
    db: Session, order: Order, delivery_date: date | None = None, notes: str | None = None,
) -> Albara:
    """Idempotent: si la comanda ja té un albarà, el retorna tal qual en
    comptes de duplicar-lo. NO fa commit — qui ho crida ha de fer-ho (i
    capturar IntegrityError si dues crides concurrents hi arriben alhora,
    ja que `order_id` és únic a nivell de BD, última línia de defensa)."""
    existent = db.scalar(select(Albara).where(Albara.order_id == order.id))
    if existent is not None:
        return existent

    dia = delivery_date or date.today()
    fiscal_year = dia.year
    albara = Albara(
        fiscal_year=fiscal_year, number=next_document_number(db, "albara", fiscal_year),
        order_id=order.id, delivery_date=dia, notes=notes,
    )
    db.add(albara)
    db.flush()
    return albara
