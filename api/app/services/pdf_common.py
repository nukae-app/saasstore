"""Capçalera compartida (dades fiscals de l'empresa) per als PDF de
documents comercials nous (Bloc B1, veure docs/PLAN_PARIDAD_HOLDED.md):
pressupostos, albarans i factura de compra. `comanda_pdf.py` i
`recepcio_pdf.py` no la fan servir perquè són anteriors a aquesta extracció
— mateix contingut, no es toquen per no barrejar un canvi no relacionat amb
aquesta feina."""

from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ConfiguracioBotiga


def new_pdf_with_header(db: Session) -> FPDF:
    config = db.scalar(select(ConfiguracioBotiga))
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, config.fiscal_name if config else "", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    if config:
        if config.nif:
            pdf.cell(0, 5, f"NIF: {config.nif}", new_x="LMARGIN", new_y="NEXT")
        for linia in (config.address or "").splitlines():
            pdf.cell(0, 5, linia, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    return pdf
