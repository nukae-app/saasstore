"""Crea les pàgines per defecte al CMS i assigna tots els posts existents a la pàgina 'blog'.

Idempotent: torna a executar sense problemes.

Ús:
    docker compose exec api python -m scripts.seed_pagines
"""

from app.database import SessionLocal
from app.models import Pagina, Post, PostPagina
from sqlalchemy import select

DEFAULT_PAGES = [
    {"slug": "blog",    "nom": "Blog",    "tipus": "llista-posts", "posicio": 1},
    {"slug": "agenda",  "nom": "Agenda",  "tipus": "agenda",       "posicio": 2},
]


def main():
    db = SessionLocal()

    for data in DEFAULT_PAGES:
        existing = db.scalar(select(Pagina).where(Pagina.slug == data["slug"]))
        if existing:
            print(f"  · {data['slug']} ja existeix, saltant")
            continue
        pagina = Pagina(**data)
        db.add(pagina)
        db.flush()
        print(f"  + Creada pàgina: {data['slug']} (id={pagina.id})")

    db.commit()

    # Assignar tots els posts publicats a la pàgina 'blog' si no estan assignats ja
    blog = db.scalar(select(Pagina).where(Pagina.slug == "blog"))
    if blog:
        posts = db.scalars(select(Post).where(Post.publicado_at.is_not(None))).all()
        assigned = 0
        for post in posts:
            exists = db.scalar(
                select(PostPagina).where(
                    PostPagina.post_id == post.id,
                    PostPagina.pagina_id == blog.id,
                )
            )
            if not exists:
                db.add(PostPagina(post_id=post.id, pagina_id=blog.id))
                assigned += 1
        db.commit()
        print(f"  + {assigned} posts assignats a 'blog'")

    db.close()
    print("Fet.")


if __name__ == "__main__":
    main()
