"""Pull de comandes del Marketplace de Discogs cap a la taula `orders` (origen='discogs').

Pensat per cron al VPS, p. ex. cada 20 minuts:
    */20 * * * * cd /home/ubuntu/recordshop && docker compose exec -T api python -m scripts.sync_discogs_orders >> /var/log/discogs_orders_sync.log 2>&1

També es pot disparar a demanda des de l'admin (POST /admin/discogs/sync/orders).
"""

from app.database import SessionLocal
from app.services.discogs_sync import sync_discogs_orders


def main() -> None:
    db = SessionLocal()
    try:
        resum = sync_discogs_orders(db)
        print(f"Discogs orders sync: {resum}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
