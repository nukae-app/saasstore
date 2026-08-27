"""Traducción de textos de emails transaccionales, reutilizando la misma
tabla `translations` que ya sirve la UI del admin (ver routers/i18n.py y
scripts/seed_translations.py, namespace `email.*`)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Tenant, Translation
from ..tenancy import tenant_frontend_url
from .email_translations import EMAIL_TRANSLATIONS


def translate(db: Session, key: str, lang: str, **kwargs) -> str:
    row = db.scalar(select(Translation).where(Translation.key == key, Translation.lang == lang))
    if row is None and lang != "ca":
        row = db.scalar(select(Translation).where(Translation.key == key, Translation.lang == "ca"))
    if row is not None:
        text = row.value
    else:
        # BD sin sembrar (o clave nueva sin desplegar aún): cae al texto en
        # código, nunca a la clave cruda — un email no debe enseñar "email.foo.bar".
        langs = EMAIL_TRANSLATIONS.get(key, {})
        text = langs.get(lang) or langs.get("ca") or key
    return text.format(**kwargs) if kwargs else text


def frontend_url(path: str, lang: str, tenant: Tenant) -> str:
    return f"{tenant_frontend_url(tenant)}/{lang}{path}"
