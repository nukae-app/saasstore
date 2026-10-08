"""Generació del PDF de recepció, a partir del model Compra.

A diferència del PDF de comanda (comanda_pdf.py, que es fa servir per demanar
mercaderia al proveïdor amb el cost estimat), aquest reflecteix el cost real i
el PVP que s'han fixat en registrar la recepció, amb el marge resultant — es
fa servir per escriure a mà les etiquetes de preu físic de cada exemplar.
"""

from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CondicionItem, Compra, ConfiguracioBotiga
from .preu_compra import iva_defecte_pct, marge_pct, recarrec_config_pct, recarrec_pct


def _files(compra: Compra):
    """(release, condició, estat disc, unitats, cost unitari, PVP) de cada fila.

    Recepcions noves: el detall guardat a `CompraLinea` (el que va entrar en
    AQUESTA recepció). Recepcions anteriors, sense línies: es recalcula des de
    `Compra.items`, que per a discos nous és el stock agregat (unitats i cost
    mitjà acumulats, no només el d'aquesta entrega)."""
    if compra.lineas:
        return [
            (l.release, l.condition, l.estado_disco, l.quantity, l.acquisition_cost, l.price)
            for l in compra.lineas
        ]
    return [
        (i.release, i.condition.value, i.estado_disco, i.quantity, i.acquisition_cost, i.price)
        for i in compra.items
    ]


def generate_recepcio_pdf(compra: Compra, db: Session) -> bytes:
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
        for linia in config.address.splitlines():
            pdf.cell(0, 5, linia, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, "Llista de recepció", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, f"Data: {compra.date.strftime('%d/%m/%Y')}", new_x="LMARGIN", new_y="NEXT")
    proveidor = compra.proveedor.name if compra.proveedor else (compra.individual_name or "")
    pdf.cell(0, 5, f"Proveïdor: {proveidor}", new_x="LMARGIN", new_y="NEXT")
    if compra.delivery_note_number:
        pdf.cell(0, 5, f"Albarà: {compra.delivery_note_number}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    col_widths = (62, 22, 12, 28, 26, 30)
    headers = ("Disc", "Estat", "Ut.", "Preu compra", "% Marge", "PVP")
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, h, border=1, fill=True)
    pdf.ln()

    iva = {c.value: iva_defecte_pct(db, c) for c in CondicionItem}
    recarrec = recarrec_config_pct(db)
    pdf.set_font("Helvetica", "", 9)
    total_cost = 0
    total_pvp = 0
    for release, condition, estado_disco, quantity, cost, price in _files(compra):
        descripcio = f"{release.artista} - {release.title}"
        estat = "Nou" if condition == CondicionItem.nou.value else "2a mà"
        if estado_disco:
            estat += f" · {estado_disco}"
        marge = marge_pct(price, cost, condition, iva[condition], recarrec)
        total_cost += (cost or 0) * quantity
        total_pvp += price * quantity
        pdf.cell(col_widths[0], 7, descripcio[:34], border=1)
        pdf.cell(col_widths[1], 7, estat[:14], border=1)
        pdf.cell(col_widths[2], 7, str(quantity), border=1, align="C")
        pdf.cell(col_widths[3], 7, f"{cost:.2f} EUR" if cost is not None else "-", border=1, align="R")
        pdf.cell(col_widths[4], 7, f"{marge:.1f} %" if marge is not None else "-", border=1, align="R")
        pdf.cell(col_widths[5], 7, f"{price:.2f} EUR", border=1, align="R")
        pdf.ln()

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(sum(col_widths[:3]), 7, "Total", border=1, align="R")
    pdf.cell(col_widths[3], 7, f"{total_cost:.2f} EUR", border=1, align="R")
    pdf.cell(col_widths[4], 7, "", border=1)
    pdf.cell(col_widths[5], 7, f"{total_pvp:.2f} EUR", border=1, align="R")
    pdf.ln(10)

    pdf.set_font("Helvetica", "", 8)
    nota = "Preu de compra per unitat, sense IVA."
    if any(recarrec_pct(f[1], recarrec) for f in _files(compra)):
        nota += f" Marge calculat sobre el cost amb recàrrec d'equivalència ({recarrec:g} %) per als discos nous."
    nota += " PVP amb IVA inclòs."
    pdf.multi_cell(0, 4, nota)

    return bytes(pdf.output())
