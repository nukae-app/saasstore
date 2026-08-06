"""Generació del PDF de comanda a proveïdor, a partir del model Comanda."""

from fpdf import FPDF
from sqlalchemy.orm import Session

from ..models import Comanda, ConfiguracioBotiga


def generate_comanda_pdf(comanda: Comanda, db: Session) -> bytes:
    config = db.get(ConfiguracioBotiga, 1)
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, config.nom_fiscal if config else "", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    if config:
        if config.nif:
            pdf.cell(0, 5, f"NIF: {config.nif}", new_x="LMARGIN", new_y="NEXT")
        for linia in config.adreca.splitlines():
            pdf.cell(0, 5, linia, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 14)
    titol = f"Comanda {comanda.num_comanda}" if comanda.num_comanda else "Comanda"
    pdf.cell(0, 8, titol, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, f"Data: {comanda.fecha.strftime('%d/%m/%Y')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Proveïdor: {comanda.proveedor.nombre}", new_x="LMARGIN", new_y="NEXT")
    if comanda.notas:
        pdf.cell(0, 5, f"Notes: {comanda.notas}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    col_widths = (90, 25, 35, 35)
    headers = ("Disc", "Quantitat", "Preu unitari", "Subtotal")
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, h, border=1, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    total = 0
    for linea in comanda.lineas:
        descripcio = f"{linea.release.artista} - {linea.release.titulo}"
        preu = linea.precio_unitario_estimado
        subtotal = (preu * linea.cantidad) if preu is not None else None
        if subtotal is not None:
            total += subtotal
        pdf.cell(col_widths[0], 7, descripcio[:55], border=1)
        pdf.cell(col_widths[1], 7, str(linea.cantidad), border=1, align="C")
        pdf.cell(col_widths[2], 7, f"{preu:.2f} EUR" if preu is not None else "-", border=1, align="R")
        pdf.cell(col_widths[3], 7, f"{subtotal:.2f} EUR" if subtotal is not None else "-", border=1, align="R")
        pdf.ln()

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(sum(col_widths[:3]), 7, "Total estimat", border=1, align="R")
    pdf.cell(col_widths[3], 7, f"{total:.2f} EUR", border=1, align="R")

    return bytes(pdf.output())
