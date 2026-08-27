"""Omple el camp ean dels releases existents consultant Discogs.

Processa només els releases que tenen discogs_release_id però encara no
tenen ean. Ritme: ~55 peticions/minut (throttle incorporat al servei).

Ús:
  docker compose exec api python -m scripts.backfill_ean --tenant recordstore
  docker compose exec api python -m scripts.backfill_ean --tenant recordstore --force   # re-consulta tots
  docker compose exec api python -m scripts.backfill_ean --tenant recordstore --limit 100
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
from sqlalchemy import select


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", required=True, help="Slug del tenant (ver tabla tenants)")
    parser.add_argument("--force", action="store_true",
                        help="Re-consulta fins i tot els que ja tenen ean")
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
        stmt = stmt.where(Release.ean.is_(None))
    stmt = stmt.order_by(RecordProduct.artista)

    releases = db.scalars(stmt).all()
    total = len(releases)
    if args.limit:
        releases = releases[: args.limit]

    print(f"Releases a processar: {len(releases)} (de {total} sense ean)")
    if not releases:
        print("Res a fer.")
        return

    ok = sense_ean = errors = 0
    for i, r in enumerate(releases, 1):
        for attempt in range(4):
            try:
                data = discogs.get_release(token, r.discogs_release_id)
                if data.get("ean"):
                    r.ean = data["ean"]
                    ok += 1
                else:
                    sense_ean += 1
                db.flush()
                if i % 10 == 0 or i == len(releases):
                    db.commit()
                    pct = i / len(releases) * 100
                    print(f"  [{i}/{len(releases)} {pct:.0f}%] {r.artista} — {r.title}: {r.ean or '(sense EAN a Discogs)'}", flush=True)
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
    print(f"\nFet: {ok} amb EAN, {sense_ean} sense EAN a Discogs, {errors} errors.")


if __name__ == "__main__":
    main()
