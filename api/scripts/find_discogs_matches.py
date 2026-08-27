"""Vincula automàticament amb Discogs els releases donats d'alta a mà (sense
discogs_release_id) — p. ex. discos rars que quan es van donar d'alta encara
no estaven catalogats a Discogs, però ja estan publicats a la nostra web.

Quan troba un match EXACTE (artista + títol) per cerca (GET /database/search,
mai escriu res a Discogs): fixa discogs_release_id i importa tracklist,
crèdits i la resta de metadades (mateixa lògica que `PUT
/admin/discogs/sync/releases/{id}/enrich`, reutilitzada aquí). Els matches
ambigus només es llisten per revisar/vincular a mà des de l'admin (camp
discogs_release_id editable al formulari d'edició).

Ús:
  docker compose exec api python -m scripts.find_discogs_matches --tenant recordstore
  docker compose exec api python -m scripts.find_discogs_matches --tenant recordstore --dry-run
  docker compose exec api python -m scripts.find_discogs_matches --tenant recordstore --limit 20
"""

import argparse

from sqlalchemy import select

from app.database import SessionLocal
from app.models import RecordProduct, Release, Tenant
from app.services import discogs
from app.services.discogs_sync import enrich_release_from_discogs
from app.tenancy import scoped_to
from app.tenant_secrets import get_tenant_secrets


def _es_match_exacte(release: Release, candidato: dict) -> bool:
    return (
        (candidato.get("artista") or "").strip().lower() == release.artista.strip().lower()
        and (candidato.get("titulo") or "").strip().lower() == release.title.strip().lower()
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tenant", required=True, help="Slug del tenant (ver tabla tenants)")
    parser.add_argument("--dry-run", action="store_true", help="només mostra els matches, no vincula ni enriqueix")
    parser.add_argument("--limit", type=int, default=0, help="processa només N releases (per provar)")
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
    releases = db.scalars(
        select(Release).join(RecordProduct)
        .where(RecordProduct.discogs_release_id.is_(None)).order_by(RecordProduct.artista)
    ).all()
    if args.limit:
        releases = releases[: args.limit]

    print(f"Releases sense discogs_release_id: {len(releases)}\n")

    vinculats = amb_candidats = sense_candidats = errors = 0
    for i, release in enumerate(releases, 1):
        query = f"{release.artista} {release.title}"
        try:
            candidatos = discogs.search_releases(token, query, per_page=5)
        except Exception as exc:
            errors += 1
            print(f"[{i}/{len(releases)}] {release.artista} — {release.title}: ERROR cercant ({exc})")
            continue

        if not candidatos:
            sense_candidats += 1
            continue

        exacte = next((c for c in candidatos if _es_match_exacte(release, c)), None)
        if exacte:
            if args.dry_run:
                vinculats += 1
                print(
                    f"[MATCH EXACTE, dry-run] {release.artista} — {release.title}  "
                    f"(local {release.id}) -> discogs_release_id={exacte['discogs_release_id']}"
                )
                continue
            release.discogs_release_id = exacte["discogs_release_id"]
            db.commit()
            ok = enrich_release_from_discogs(release, db, token)
            vinculats += 1
            estat = "vinculat + enriquit" if ok else "vinculat (error enriquint, reintenta més tard)"
            print(
                f"[{estat}] {release.artista} — {release.title}  "
                f"(local {release.id}) -> discogs_release_id={release.discogs_release_id}"
            )
        else:
            amb_candidats += 1
            print(f"[revisar a mà] {release.artista} — {release.title}  (local {release.id})")
            for c in candidatos[:3]:
                print(
                    f"    ? discogs_release_id={c['discogs_release_id']}  "
                    f"{c.get('artista')} — {c.get('titulo')}  ({c.get('anio')}, {c.get('sello')})"
                )

    print(
        f"\nFet: {vinculats} vinculats i enriquits, {amb_candidats} amb candidats a revisar a mà, "
        f"{sense_candidats} sense cap resultat a Discogs, {errors} errors."
    )


if __name__ == "__main__":
    main()
