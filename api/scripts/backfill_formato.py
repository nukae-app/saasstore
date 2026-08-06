"""Omple/neteja el camp formato dels releases existents consultant Discogs.

Processa els releases que tenen discogs_release_id i o bé no tenen formato,
o bé el tenen "brut" (text lliure heretat d'abans del mapeig a valors
canònics, p. ex. "LP, Album, Ltd, RSD" en lloc de "LP") — complementari a
find_discogs_matches.py, que només vincula releases SENSE discogs_release_id.
Ritme: ~55 peticions/minut (throttle incorporat al servei).

Ús:
  docker compose exec api python -m scripts.backfill_formato
  docker compose exec api python -m scripts.backfill_formato --force   # re-consulta fins i tot els ja nets
  docker compose exec api python -m scripts.backfill_formato --limit 100
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models import Release
from app.services import discogs
from app.services.discogs import FORMATS_CANONICS
from sqlalchemy import or_, select


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="Re-consulta fins i tot els que ja tenen un format canònic")
    parser.add_argument("--limit", type=int, default=0,
                        help="Màxim de releases a processar (0 = tots)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stmt = select(Release).where(Release.discogs_release_id.isnot(None))
        if not args.force:
            stmt = stmt.where(
                or_(Release.formato.is_(None), Release.formato.notin_(FORMATS_CANONICS))
            )
        stmt = stmt.order_by(Release.artista)

        releases = db.scalars(stmt).all()
        total = len(releases)
        if args.limit:
            releases = releases[: args.limit]

        print(f"Releases a processar: {len(releases)} (de {total} sense formato net)")
        if not releases:
            print("Res a fer.")
            return

        ok = sense_formato = errors = 0
        for i, r in enumerate(releases, 1):
            for attempt in range(4):
                try:
                    data = discogs.get_release(r.discogs_release_id)
                    if data.get("formato"):
                        r.formato = data["formato"]
                        ok += 1
                    else:
                        sense_formato += 1
                    db.flush()
                    if i % 10 == 0 or i == len(releases):
                        db.commit()
                        pct = i / len(releases) * 100
                        print(f"  [{i}/{len(releases)} {pct:.0f}%] {r.artista} — {r.titulo}: {r.formato or '(sense format a Discogs)'}", flush=True)
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
        print(f"\nFet: {ok} amb format, {sense_formato} sense format a Discogs, {errors} errors.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
