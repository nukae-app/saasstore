"""Backfill coste_adquisicion per ítems sense cost.

Per a items que ja estan al catàleg sense cost d'adquisició registrat,
estableix coste_adquisicion = precio - 2.00 (mínim 0.01).

Ús: cd api && python scripts/backfill_coste_adquisicion.py [--dry-run]
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from sqlalchemy import select, update
from app.database import SessionLocal
from app.models import Item


def main(dry_run: bool = False) -> None:
    db = SessionLocal()
    try:
        items = db.scalars(
            select(Item).where(Item.coste_adquisicion.is_(None))
        ).all()

        if not items:
            print("Cap ítem sense cost. Res a fer.")
            return

        print(f"Ítems sense cost: {len(items)}")
        updated = 0
        for item in items:
            cost = max(item.precio - Decimal("2.00"), Decimal("0.01"))
            if dry_run:
                print(f"  {item.id}: precio={item.precio} → coste={cost}")
            else:
                item.coste_adquisicion = cost
            updated += 1

        if dry_run:
            print(f"[DRY RUN] S'haurien actualitzat {updated} ítems.")
        else:
            db.commit()
            print(f"Actualitzats {updated} ítems.")
    finally:
        db.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    main(dry_run=dry_run)
