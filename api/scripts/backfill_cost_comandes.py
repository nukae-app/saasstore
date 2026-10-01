"""Omple el cost de compra de línies de comanda que es van crear sense preu.

Abans de fer-lo obligatori, resoldre una sol·licitud de compra podia crear
línies amb `estimated_unit_price` NULL (PDF amb «Sense preu», cost buit a la
recepció). Aquest script en suggereix el valor a partir de l'últim
`Item.acquisition_cost` conegut del mateix release (el mateix criteri que
`GET /admin/solicitudes-compra/ultims-costos`).

Només toca línies PENDENTS de rebre (received_quantity < quantity): a les ja
rebudes el cost real ja viu als ítems d'estoc i el preu de la comanda és només
informatiu. Les línies sense cap cost conegut es llisten perquè s'omplin a mà.

Per defecte NO escriu res (simulació). Amb --apply fa els canvis.

Ús (dins el contenedor api):

    python -m scripts.backfill_cost_comandes --tenant <slug>            # simulació
    python -m scripts.backfill_cost_comandes --tenant <slug> --apply    # escriu
"""

import argparse

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Comanda, ComandaLinea, Item, Release, Tenant
from app.tenancy import scoped_to


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", required=True, help="slug del tenant")
    parser.add_argument("--apply", action="store_true", help="escriu els canvis (per defecte, només simula)")
    args = parser.parse_args()

    db = SessionLocal()
    tenant = db.scalar(select(Tenant).where(Tenant.slug == args.tenant))
    if tenant is None:
        raise SystemExit(f"No existe ningún tenant con slug '{args.tenant}'")

    with scoped_to(db, tenant.id):
        rows = db.execute(
            select(ComandaLinea, Comanda, Release)
            .join(Comanda, Comanda.id == ComandaLinea.comanda_id)
            .join(Release, Release.id == ComandaLinea.release_id)
            .where(ComandaLinea.estimated_unit_price.is_(None))
            .order_by(Comanda.date)
        ).all()

        omplertes = sense_cost = ja_rebudes = 0
        for linea, comanda, release in rows:
            nom = f"{release.artista} - {release.title}"[:50]
            etiqueta = f"{comanda.order_number or comanda.id} · {comanda.status.value} · {nom}"
            if linea.received_quantity >= linea.quantity:
                ja_rebudes += 1
                print(f"  [rebuda, no es toca] {etiqueta}")
                continue
            cost = db.scalar(
                select(Item.acquisition_cost)
                .where(Item.release_id == linea.release_id, Item.acquisition_cost.isnot(None))
                .order_by(func.coalesce(Item.entry_date, Item.created_at).desc())
                .limit(1)
            )
            if cost is None:
                sense_cost += 1
                print(f"  [SENSE COST CONEGUT, omplir a mà] {etiqueta}")
                continue
            omplertes += 1
            print(f"  [{'omplerta' if args.apply else 'ompliria'}: {cost} €] {etiqueta}")
            if args.apply:
                linea.estimated_unit_price = cost

        if args.apply:
            db.commit()
        else:
            db.rollback()

    print(
        f"\n{len(rows)} línies sense preu · {omplertes} {'omplertes' if args.apply else 'es ompliran'} · "
        f"{sense_cost} sense cost conegut · {ja_rebudes} ja rebudes (no es toquen)"
    )
    if not args.apply:
        print("Simulació: no s'ha escrit res. Afegeix --apply per aplicar-ho.")


if __name__ == "__main__":
    main()
