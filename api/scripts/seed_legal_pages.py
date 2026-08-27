"""Crea (o actualiza) las páginas estáticas de política de privacidad y
términos de uso para un tenant.

Uso:
    docker compose exec api python -m scripts.seed_legal_pages --tenant recordstore

Idempotente: si el slug ya existe para ese tenant, actualiza el contenido
en vez de duplicar.

Fase 3 (ver plan, sección D.2): `Pagina` es ahora TenantScoped —
`--tenant` es obligatorio, mismo patrón que scripts/sync_discogs_inventory.py.
El nombre de la tienda se toma de `ConfiguracioBotiga.fiscal_name` en vez de
estar hardcodeado. El contenido es deliberadamente genérico (sin cláusula
de Spotify) — el texto específico de Spotify que tenía el tenant
`recordstore` (necesario para el Extended Quota Mode) es contenido curado a
mano para ese tenant concreto, no algo que este seed genérico deba
reproducir para cada tenant nuevo.
"""

import argparse

from sqlalchemy import select

from app.database import SessionLocal
from app.models import ConfiguracioBotiga, Pagina, Tenant
from app.tenancy import scoped_to

PRIVACITAT_TEMPLATE = """
<p>{nom} ("nosaltres") tracta les teves dades personals amb la finalitat de
gestionar la teva compra i el teu compte d'usuari.</p>

<h2>Quines dades recollim</h2>
<ul>
  <li>Dades de compte: nom, email, adreces d'enviament.</li>
  <li>Dades de comanda: articles comprats, historial de comandes.</li>
</ul>

<h2>Amb qui compartim les dades</h2>
<p>No venem ni cedim les teves dades a tercers amb finalitats comercials.
Utilitzem proveïdors de servei (allotjament, processament de pagaments,
enviament d'emails) únicament per prestar el servei.</p>

<h2>Els teus drets</h2>
<p>Pots exercir els drets d'accés, rectificació, supressió i portabilitat
escrivint a <a href="mailto:{email}">{email}</a>.</p>
""".strip()

TERMES_TEMPLATE = """
<p>L'ús d'aquesta web i la compra a {nom} implica l'acceptació d'aquests
termes.</p>

<h2>Comandes i pagament</h2>
<p>Una comanda es confirma un cop rebut el pagament. Els preus inclouen IVA.</p>

<h2>Contacte</h2>
<p><a href="mailto:{email}">{email}</a></p>
""".strip()


def seed(db, tenant_id) -> list[str]:
    """Importable desde routers/superadmin.py (alta de tenant) además del
    CLI de abajo."""
    config = db.scalar(select(ConfiguracioBotiga))
    nom = config.fiscal_name if config and config.fiscal_name else "la nostra botiga"
    email = config.contact_email if config and config.contact_email else ""

    pages = [
        dict(
            slug="privacitat", name="Política de privacitat", type="estatica",
            position=90, menu_visible=False,
            content=PRIVACITAT_TEMPLATE.format(nom=nom, email=email),
        ),
        dict(
            slug="termes", name="Termes d'ús", type="estatica",
            position=91, menu_visible=False,
            content=TERMES_TEMPLATE.format(nom=nom, email=email),
        ),
    ]

    result = []
    for data in pages:
        pagina = db.scalar(select(Pagina).where(Pagina.slug == data["slug"]))
        if pagina:
            for k, v in data.items():
                setattr(pagina, k, v)
            result.append(f"Actualitzada: /{data['slug']}")
        else:
            db.add(Pagina(**data))
            result.append(f"Creada: /{data['slug']}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tenant", required=True, help="Slug del tenant (ver tabla tenants)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == args.tenant))
        if tenant is None:
            raise SystemExit(f"No existe ningún tenant con slug '{args.tenant}'")
        with scoped_to(db, tenant.id):
            for line in seed(db, tenant.id):
                print(line)
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
