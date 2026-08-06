"""Generació del PDF de recepció, a partir del model Compra.

A diferència del PDF de comanda (comanda_pdf.py, que es fa servir per demanar
mercaderia al proveïdor amb el preu estimat), aquest reflecteix el preu de
venda real que s'ha fixat en registrar la recepció — es fa servir per
escriure a mà les etiquetes de preu físic de cada exemplar rebut.
"""

from fpdf import FPDF
from sqlalchemy.orm import Session

from ..models import CondicionItem, Compra, ConfiguracioBotiga


def generate_recepcio_pdf(compra: Compra, db: Session) -> bytes:
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
    pdf.cell(0, 8, "Llista de recepció", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, f"Data: {compra.fecha.strftime('%d/%m/%Y')}", new_x="LMARGIN", new_y="NEXT")
    proveidor = compra.proveedor.nombre if compra.proveedor else (compra.nombre_particular or "")
    pdf.cell(0, 5, f"Proveïdor: {proveidor}", new_x="LMARGIN", new_y="NEXT")
    if compra.num_albaran:
        pdf.cell(0, 5, f"Albarà: {compra.num_albaran}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    col_widths = (100, 45, 35)
    headers = ("Disc", "Estat", "Preu venda")
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, h, border=1, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    total = 0
    for item in compra.items:
        descripcio = f"{item.release.artista} - {item.release.titulo}"
        estat = "Nou" if item.condicion == CondicionItem.nou else "2a mà"
        if item.estado_disco:
            estat += f" · {item.estado_disco}"
        total += item.precio
        pdf.cell(col_widths[0], 7, descripcio[:50], border=1)
        pdf.cell(col_widths[1], 7, estat[:28], border=1)
        pdf.cell(col_widths[2], 7, f"{item.precio:.2f} EUR", border=1, align="R")
        pdf.ln()

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(sum(col_widths[:2]), 7, "Total", border=1, align="R")
    pdf.cell(col_widths[2], 7, f"{total:.2f} EUR", border=1, align="R")

    return bytes(pdf.output())
