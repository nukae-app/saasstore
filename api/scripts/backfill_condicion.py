"""Reclassifica items existents com a nou/segona_ma segons el seu grading
(estado_disco), amb la mateixa regla que ja fa servir la sincronització del
catàleg (veure services/catalog_sync.derive_condicion): Mint/Near Mint -> nou,
la resta -> segona_ma.

Ús:
  docker compose exec api python -m scripts.backfill_condicion            # aplica
  docker compose exec api python -m scripts.backfill_condicion --dry-run  # només mostra
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models import Item
from app.services.catalog_sync import derive_condicion
from sqlalchemy import select


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Mostra els canvis sense desar-los")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        items = db.scalars(select(Item)).all()
        canvis = 0
        for item in items:
            nova = derive_condicion(item.estado_disco)
            if nova != item.condition:
                canvis += 1
                if not args.dry_run:
                    item.condition = nova

        print(f"Items revisats: {len(items)}. Canvis {'a aplicar' if args.dry_run else 'aplicats'}: {canvis}")
        if not args.dry_run:
            db.commit()
        else:
            db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
