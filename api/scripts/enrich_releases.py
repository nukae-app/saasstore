"""Enriqueix releases existents amb tracklist, crèdits, país, estils i gènere de Discogs.

Processa només els releases que tenen discogs_release_id i els falta
tracklist o gènere (aquest últim es va afegir després, per això molts
releases ja "enriquits" abans no el tenen).
Ritme: ~55 peticions/minut (throttle incorporat al servei).

Ús:
  docker compose exec api python -m scripts.enrich_releases --tenant recordstore
  docker compose exec api python -m scripts.enrich_releases --tenant recordstore --force   # re-enriqueix tots
  docker compose exec api python -m scripts.enrich_releases --tenant recordstore --limit 100
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models import RecordProduct, Release, Tenant
from app.services import discogs
from app.tenancy import scoped_to
from app.tenant_secrets import get_tenant_secrets
from sqlalchemy import or_, select


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", required=True, help="Slug del tenant (ver tabla tenants)")
    parser.add_argument("--force", action="store_true",
                        help="Re-enriqueix fins i tot els que ja tenen tracklist")
    parser.add_argument("--limit", type=int, default=0,
                        help="Màxim de releases a processar (0 = tots)")
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
    token = get_tenant_secrets(tenant.id).discogs_token
    stmt = select(Release).join(RecordProduct).where(RecordProduct.discogs_release_id.isnot(None))
    if not args.force:
        stmt = stmt.where(or_(RecordProduct.tracklist.is_(None), RecordProduct.genero.is_(None)))
    stmt = stmt.order_by(RecordProduct.artista)

    releases = db.scalars(stmt).all()
    total = len(releases)
    if args.limit:
        releases = releases[: args.limit]

    print(f"Releases a enriquir: {len(releases)} (de {total} amb discogs_release_id)")
    if not releases:
        print("Res a fer.")
        return

    ok = errors = 0
    for i, r in enumerate(releases, 1):
        for attempt in range(4):
            try:
                data = discogs.get_release(token, r.discogs_release_id)
                r.tracklist = data.get("tracklist") or None
                r.credits   = data.get("credits") or None
                r.pais      = r.pais   or data.get("pais")
                r.estilos   = r.estilos or data.get("estilos")
                r.genero    = r.genero or data.get("genero")
                if not r.image_url and data.get("imagen_url"):
                    r.image_url = data["imagen_url"]
                if not r.sello and data.get("sello"):
                    r.sello = data["sello"]
                db.flush()
                ok += 1
                if i % 10 == 0 or i == len(releases):
                    db.commit()
                    pct = i / len(releases) * 100
                    print(f"  [{i}/{len(releases)} {pct:.0f}%] {r.artista} — {r.title}", flush=True)
                break
            except Exception as exc:
                msg = str(exc)
                if "429" in msg:
                    wait = 65 * (attempt + 1)
                    print(f"  429 rate limit — esperant {wait}s (intent {attempt+1}/4)...", flush=True)
                    import time as _t; _t.sleep(wait)
                else:
                    errors += 1
                    print(f"  ERROR {r.discogs_release_id} ({r.artista}): {exc}", file=sys.stderr, flush=True)
                    db.rollback()
                    break

    db.commit()
    print(f"\nFet: {ok} enriquits, {errors} errors.")


if __name__ == "__main__":
    main()
