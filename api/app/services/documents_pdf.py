"""Generació de PDF per als documents comercials del Bloc B1 (veure
docs/PLAN_PARIDAD_HOLDED.md): pressupostos, albarans i factura de compra
(sobre `Despesa`, sense taula pròpia). Mateix patró que comanda_pdf.py /
recepcio_pdf.py — fpdf2, sense dependències natives com WeasyPrint."""

from .pdf_common import new_pdf_with_header
from ..models import Albara, CondicionItem, Despesa, Pressupost


def generate_pressupost_pdf(pressupost: Pressupost, db) -> bytes:
    pdf = new_pdf_with_header(db)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, f"Pressupost {pressupost.fiscal_year}/{pressupost.number:04d}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, f"Data: {pressupost.issue_date.strftime('%d/%m/%Y')}", new_x="LMARGIN", new_y="NEXT")
    if pressupost.valid_until:
        pdf.cell(0, 5, f"Vàlid fins: {pressupost.valid_until.strftime('%d/%m/%Y')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Client: {pressupost.client_name}", new_x="LMARGIN", new_y="NEXT")
    if pressupost.client_email:
        pdf.cell(0, 5, f"Email: {pressupost.client_email}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    col_widths = (90, 20, 25, 20, 35)
    headers = ("Descripció", "Quant.", "Preu unit.", "IVA", "Subtotal")
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, h, border=1, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    total_base = 0
    total_iva = 0
    for linia in pressupost.lines:
        subtotal = linia.quantity * linia.unit_price
        iva_import = subtotal * linia.vat_pct / 100
        total_base += subtotal
        total_iva += iva_import
        pdf.cell(col_widths[0], 7, linia.description[:55], border=1)
        pdf.cell(col_widths[1], 7, f"{linia.quantity:.2f}", border=1, align="R")
        pdf.cell(col_widths[2], 7, f"{linia.unit_price:.2f}", border=1, align="R")
        pdf.cell(col_widths[3], 7, f"{linia.vat_pct:.0f}%", border=1, align="R")
        pdf.cell(col_widths[4], 7, f"{subtotal:.2f} EUR", border=1, align="R")
        pdf.ln()

    total = total_base + total_iva
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(sum(col_widths[:4]), 7, "Base imposable", border=1, align="R")
    pdf.cell(col_widths[4], 7, f"{total_base:.2f} EUR", border=1, align="R")
    pdf.ln()
    pdf.cell(sum(col_widths[:4]), 7, "IVA", border=1, align="R")
    pdf.cell(col_widths[4], 7, f"{total_iva:.2f} EUR", border=1, align="R")
    pdf.ln()
    pdf.cell(sum(col_widths[:4]), 7, "Total", border=1, align="R")
    pdf.cell(col_widths[4], 7, f"{total:.2f} EUR", border=1, align="R")

    return bytes(pdf.output())


def generate_albara_pdf(albara: Albara, db) -> bytes:
    pdf = new_pdf_with_header(db)
    order = albara.order

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, f"Albarà {albara.fiscal_year}/{albara.number:04d}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, f"Data d'entrega: {albara.delivery_date.strftime('%d/%m/%Y')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Comanda: #{str(order.id)[:8]}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Client: {order.contact_email}", new_x="LMARGIN", new_y="NEXT")
    if albara.notes:
        pdf.cell(0, 5, f"Notes: {albara.notes}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    col_widths = (140, 25, 25)
    headers = ("Disc", "Quant.", "Condició")
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, h, border=1, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    for linia in order.items:
        descripcio = f"{linia.release.artista} - {linia.release.title}" if linia.release else "-"
        condicio = "Nou" if linia.condition == CondicionItem.nou else "2a mà"
        pdf.cell(col_widths[0], 7, descripcio[:75], border=1)
        pdf.cell(col_widths[1], 7, str(linia.quantity), border=1, align="C")
        pdf.cell(col_widths[2], 7, condicio, border=1, align="C")
        pdf.ln()

    return bytes(pdf.output())


def generate_despesa_pdf(despesa: Despesa, db) -> bytes:
    """Formalitza una `Despesa` (factura de compra ja registrada) com a PDF
    — sense taula nova, veure docs/PLAN_PARIDAD_HOLDED.md bloc B1."""
    pdf = new_pdf_with_header(db)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, "Factura de compra", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    if despesa.invoice_number:
        pdf.cell(0, 5, f"Núm. factura proveïdor: {despesa.invoice_number}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Data: {despesa.invoice_date.strftime('%d/%m/%Y')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Proveïdor: {despesa.supplier_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Concepte: {despesa.concept}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    col_widths = (95, 35, 25, 35)
    headers = ("Concepte", "Base imposable", "IVA", "Total")
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, h, border=1, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    pdf.cell(col_widths[0], 7, despesa.concept[:55], border=1)
    pdf.cell(col_widths[1], 7, f"{despesa.taxable_base:.2f} EUR", border=1, align="R")
    pdf.cell(col_widths[2], 7, f"{despesa.vat_pct:.0f}%", border=1, align="R")
    pdf.cell(col_widths[3], 7, f"{despesa.total:.2f} EUR", border=1, align="R")

    return bytes(pdf.output())
