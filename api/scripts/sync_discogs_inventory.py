"""Reconcilia la BD amb l'inventari REAL del Marketplace de Discogs (compte
venedor autenticat pel token del tenant). Només fa lectura (GET) a Discogs:
mai crea, edita ni elimina cap listing.

La lògica viu a `app/services/discogs_inventory_sync.py` (compartida amb la
pantalla d'admin /admin/canals/discogs); aquest és el wrapper de línia
d'ordres.

Comportament (primera execució = adopció, "Discogs mana"; docs/PLAN_CANAL_DISCOGS.md §8):
  - Listing "For Sale" a Discogs que no existeix a la BD (per codi_discogs):
    - segona_ma -> es crea sempre un Item nou (cada còpia és única).
    - nou (stock agregat) -> si ja hi ha una línia `nou` per aquest release,
      se li suma 1 a `cantidad`; si no, es crea. ("stock virtual de 1",
      veure services/discogs_sync.py).
    - Si cal, es crea el Release consultant /releases/{id}.
  - Listing que ja existeix a la BD -> el preu es sincronitza amb el que
    digui Discogs ara mateix (condició/grading NO es toca). Discogs mana en preu.
  - Item a la BD amb status=disponible i codi_discogs que ja NO és "For Sale":
    - segona_ma -> es marca com a `retirado`.
    - nou -> es descompta 1 unitat de `cantidad` i es buida `codi_discogs`.
  - Mai toca items en estat reservado/vendido/retirado.
  - Pas previ: consolida en una sola línia els releases amb més d'una fila
    `nou` (model antic, una fila per unitat), si no tenen referències externes.

Salvaguardes:
  - Informe per ítem (CSV): sempre en --dry-run (ruta per defecte a /tmp, o la
    de --informe) i opcionalment en l'execució real. Revisa'l ABANS de la real.
  - Fre de seguretat: s'avorta (execució real) si Discogs retorna 0 listings o
    si s'hauria de retirar més del --max-retire-pct (20 %) dels ítems
    disponibles vinculats a Discogs, tret de --force. En --dry-run només avisa.
  - Marca d'adopció feta per tenant: quan una execució real acaba bé (sense
    --limit i sense errors) es registra, i a partir d'aquí l'execució real
    es nega (manda l'app) tret de --reobrir-adopcio.
  - Amb --limit NO es retira res: l'inventari estaria truncat.

Ús:
  docker compose exec api python -m scripts.sync_discogs_inventory --tenant recordstore --dry-run
  docker compose exec api python -m scripts.sync_discogs_inventory --tenant recordstore --dry-run --informe /tmp/informe.csv
  docker compose exec api python -m scripts.sync_discogs_inventory --tenant recordstore
  docker compose exec api python -m scripts.sync_discogs_inventory --tenant recordstore --limit 50

`--tenant` és obligatori: aquest script obre la seva pròpia sessió sense tenant
per defecte, i `Item`/`Release` són TenantScoped.
"""

import argparse
from datetime import datetime

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Tenant
from app.services.discogs_inventory_sync import (  # noqa: F401  (re-exportats: els tests els importen d'aquí)
    INFORME_COLUMNES, InventorySyncAbort, _consolidar_duplicados_nou, _tiene_dependientes,
    escribir_informe, run_inventory_sync,
)
from app.tenancy import scoped_to


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tenant", required=True, help="Slug del tenant (ver tabla tenants)")
    parser.add_argument("--dry-run", action="store_true", help="simula sense guardar res a la BD")
    parser.add_argument("--limit", type=int, default=0, help="processa només N listings (per provar; no retira res)")
    parser.add_argument("--informe", help="ruta del CSV amb una fila per ítem (per defecte, en --dry-run: /tmp)")
    parser.add_argument(
        "--max-retire-pct", type=float, default=20.0,
        help="avorta si s'haurien de retirar més d'aquest %% dels ítems disponibles vinculats (def. 20)",
    )
    parser.add_argument("--force", action="store_true", help="salta el fre de seguretat (0 listings / massa retirades)")
    parser.add_argument(
        "--reobrir-adopcio", action="store_true",
        help="permet una execució real encara que l'adopció ja estigui marcada com a feta",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == args.tenant))
        if tenant is None:
            raise SystemExit(f"No existe ningún tenant con slug '{args.tenant}'")
        with scoped_to(db, tenant.id):
            _run(db, tenant, args)
    finally:
        db.close()


def _run(db, tenant: Tenant, args) -> None:
    try:
        result = run_inventory_sync(
            db, tenant, dry_run=args.dry_run, limit=args.limit, max_retire_pct=args.max_retire_pct,
            force=args.force, reobrir_adopcio=args.reobrir_adopcio, log=lambda m: print(m, flush=True),
        )
    except InventorySyncAbort as exc:
        raise SystemExit(f"{exc}\n(--force per saltar el fre de seguretat; --reobrir-adopcio si l'adopció ja està feta.)")

    ruta_informe = args.informe or (
        f"/tmp/discogs_inventory_{tenant.slug}_{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
        if args.dry_run else None
    )
    if ruta_informe:
        escribir_informe(result.rows, ruta_informe)
        print(f"\nInforme per ítem ({len(result.rows)} files): {ruta_informe}", flush=True)

    s = result.summary
    etiqueta = "DRY-RUN (res guardat)" if args.dry_run else "Fet"
    print(
        f"\n{etiqueta}: {s['creats']} creats, {s['sumats']} sumats a línies nou, {s['actualitzats']} "
        f"actualitzats (preu/fecha_entrada), {s['retirats']} retirats/descomptats, {s['errors']} errors."
    )


if __name__ == "__main__":
    main()
