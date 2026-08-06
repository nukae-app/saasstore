"""Vincula comandes web fetes com a convidat (orders.user_id IS NULL) a un
compte d'usuari existent quan l'email coincideix. Idempotent: només toca
les que encara no tenen user_id.

Ús:
    docker compose exec api python -m scripts.link_orphan_orders_to_users
"""

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Order, User


def main():
    db = SessionLocal()
    try:
        orphans = db.scalars(select(Order).where(Order.user_id.is_(None))).all()
        linked = 0
        for o in orphans:
            user = db.scalar(select(User).where(func.lower(User.email) == o.email_contacto.lower()))
            if user:
                print(f"  {o.id} ({o.email_contacto}) -> usuari {user.id}")
                o.user_id = user.id
                linked += 1
        db.commit()
        print(f"RESUM: {linked} comandes vinculades de {len(orphans)} sense usuari.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
