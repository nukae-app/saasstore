"""Envío de emails. Sin SMTP configurado (dev), imprime el contenido en los logs."""

import os
import re
import smtplib
from email.message import EmailMessage

from ..config import get_settings


def absolutize_upload_urls(html: str) -> str:
    """Las imágenes subidas al editor se guardan como /uploads/... (relativo, válido en el
    panell admin). En un email no hay origen: hace falta la URL absoluta del sitio."""
    base = get_settings().frontend_url
    return re.sub(r'(src=["\'])(/uploads/)', rf"\1{base}\2", html)


def render_email_html(heading: str, body_html: str, cta: tuple[str, str] | None = None) -> str:
    """Plantilla compartida per a tots els emails transaccionals de client
    (capçalera amb el logo, mateix estil de botó ambre): confirmació de
    compte, magic link, comanda confirmada i el flux de peticions. La
    newsletter no la fa servir (és HTML lliure editat a l'admin)."""
    logo_url = f"{get_settings().frontend_url}/logo.png"
    cta_html = ""
    if cta:
        label, url = cta
        cta_html = f"""
      <p style="text-align:center;margin:28px 0">
        <a href="{url}" style="background:#f59e0b;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:600;font-size:14px;display:inline-block">{label}</a>
      </p>"""
    return f"""\
<div style="background:#f4f4f5;padding:32px 16px;font-family:-apple-system,Helvetica,Arial,sans-serif">
  <div style="max-width:480px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden">
    <div style="background:#18181b;padding:24px;text-align:center">
      <img src="{logo_url}" alt="Ultra-Local Records" height="36" style="height:36px;width:auto">
    </div>
    <div style="padding:32px 28px;color:#27272a">
      <h1 style="font-size:20px;margin:0 0 12px">{heading}</h1>
      {body_html}{cta_html}
    </div>
    <div style="padding:16px 28px;border-top:1px solid #e4e4e7;text-align:center">
      <p style="font-size:11px;color:#a1a1aa;margin:0">Ultra-Local Records · Pujades 113, 08005 Barcelona</p>
    </div>
  </div>
</div>
"""


def send_email(
    to: str,
    subject: str,
    body: str,
    attachment: tuple[str, bytes, str] | None = None,
    html: str | None = None,
) -> None:
    """attachment: (nombre_fichero, contenido, maintype/subtype) p. ej. ("comanda.pdf", data, "application/pdf").
    html: versión HTML alternativa (p. ej. para newsletters); body sigue siendo el fallback en texto plano."""
    s = get_settings()
    if not s.smtp_host:
        extra = f" (amb adjunt {attachment[0]})" if attachment else ""
        if os.environ.get("AWS_SECRETS_NAME"):
            # Entorno con secretos de AWS (staging/producción): si SMTP no está
            # configurado aquí es una configuración rota, no el flujo normal de
            # dev local — no volcamos el cuerpo (puede llevar tokens/magic links).
            print(f"\n--- EMAIL (SMTP sin configurar) ---\nPara: {to}\nAsunto: {subject}{extra}\n(cuerpo omitido por seguridad)\n---\n")
        else:
            # Dev local / tests: sin SMTP, este print es el único "buzón" que
            # existe (así se documenta en CLAUDE.md) — se mantiene completo.
            print(f"\n--- EMAIL (dev, SMTP sin configurar) ---\nPara: {to}\nAsunto: {subject}{extra}\n\n{body}\n---\n")
        return
    msg = EmailMessage()
    msg["From"] = s.email_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
    if attachment:
        filename, content, content_type = attachment
        maintype, _, subtype = content_type.partition("/")
        msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)
    with smtplib.SMTP(s.smtp_host, s.smtp_port) as server:
        server.starttls()
        if s.smtp_user:
            server.login(s.smtp_user, s.smtp_password)
        server.send_message(msg)
