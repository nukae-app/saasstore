"""Enriqueix releases sense imatge consultant la API de Discogs.

Per a cada release sense `imagen_url`, agafa el `codi_discogs` d'un dels seus
ítems, consulta el listing del marketplace i actualitza la URL de la caràtula.

Dues qualitats:
  --quality thumbnail  (per defecte)  1 crida/release  ~150×150 px
  --quality full                       2 crides/release ~600×600 px  (lent)

Requisits:
  Afegeix el teu token personal de Discogs al .env:
    DISCOGS_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx
  (Obté'l a https://www.discogs.com/settings/developers → "Generate new token")
  Sense token: 25 req/min. Amb token: 60 req/min.

Ús (dins del contenidor api):
    docker compose exec api python -m scripts.enrich_images --tenant recordstore
    docker compose exec api python -m scripts.enrich_images --tenant recordstore --limit 50
    docker compose exec api python -m scripts.enrich_images --tenant recordstore --quality full
    docker compose exec api python -m scripts.enrich_images --tenant recordstore --dry-run

Es pot interrompre amb Ctrl+C i reprendre; els releases ja processats es salten.

Fase 2 (secretos por tenant): `--tenant` es obligatorio — este script abre su
propia sesión sin tenant, y `Release` es TenantScoped, así que sin esto
consultaría/tocaría releases de TODOS los tenants."""

import argparse
import sys
import time
from typing import Literal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Item, RecordProduct, RecordStockDetail, Release, Tenant
from app.tenancy import scoped_to
from app.tenant_secrets import get_tenant_secrets

BASE = "https://api.discogs.com"
USER_AGENT = "UltraLocalRecords/1.0 +https://ultralocalrecords.example"


def _headers(token: str | None) -> dict:
    h = {"User-Agent": USER_AGENT}
    if token:
        h["Authorization"] = f"Discogs token={token}"
    return h


class RateLimiter:
    def __init__(self, calls_per_min: int):
        self.interval = 60.0 / calls_per_min
        self._last = 0.0

    def wait(self):
        elapsed = time.monotonic() - self._last
        remaining = self.interval - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last = time.monotonic()


def fetch_listing(client: httpx.Client, rl: RateLimiter, listing_id: int) -> dict | None:
    """Retorna {'discogs_release_id', 'imagen_url'} o None si el listing no existeix."""
    rl.wait()
    r = client.get(f"/marketplace/listings/{listing_id}")
    if r.status_code == 404:
        return None
    if r.status_code == 429:
        print("  [rate limit] esperant 60s...")
        time.sleep(60)
        return fetch_listing(client, rl, listing_id)
    r.raise_for_status()
    data = r.json()
    rel = data.get("release", {})
    return {
        "discogs_release_id": rel.get("id"),
        "imagen_url": rel.get("thumbnail") or None,
    }


def fetch_release_image(client: httpx.Client, rl: RateLimiter, release_id: int) -> str | None:
    """Retorna la URL de la primera imatge gran del release (≥600px)."""
    rl.wait()
    r = client.get(f"/releases/{release_id}")
    if r.status_code == 404:
        return None
    if r.status_code == 429:
        print("  [rate limit] esperant 60s...")
        time.sleep(60)
        return fetch_release_image(client, rl, release_id)
    r.raise_for_status()
    images = r.json().get("images", [])
    # Preferir imatge principal (type=primary) de bona qualitat
    for img in sorted(images, key=lambda i: i.get("type") != "primary"):
        uri = img.get("uri") or img.get("uri150")
        if uri:
            return uri
    return None


def get_item_codi(db: Session, release_id) -> int | None:
    """Retorna el primer codi_discogs disponible per un release."""
    item = db.scalar(
        select(Item)
        .join(RecordStockDetail, RecordStockDetail.item_id == Item.id)
        .where(Item.release_id == release_id, RecordStockDetail.codi_discogs.isnot(None))
        .limit(1)
    )
    return item.codi_discogs if item else None


def stats(db: Session) -> tuple[int, int]:
    from sqlalchemy import func
    total = db.scalar(select(func.count(Release.id)))
    amb = db.scalar(select(func.count(Release.id)).where(Release.image_url.isnot(None)))
    return total, amb


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tenant", required=True, help="Slug del tenant (ver tabla tenants)")
    parser.add_argument("--quality", choices=["thumbnail", "full"], default="thumbnail",
                        help="thumbnail (ràpid, 150px) o full (lent, 600px+). Per defecte: thumbnail")
    parser.add_argument("--limit", type=int, default=0,
                        help="processa només N releases (per provar)")
    parser.add_argument("--dry-run", action="store_true",
                        help="simula sense guardar res a la base de dades")
    parser.add_argument("--calls-per-min", type=int, default=None,
                        help="crides API per minut. Per defecte: 55 amb token, 20 sense")
    parser.add_argument("--force", action="store_true",
                        help="reprocessa releases que ja tenen imatge (per pujar a full quality)")
    args = parser.parse_args()

    db = SessionLocal()
    tenant = db.scalar(select(Tenant).where(Tenant.slug == args.tenant))
    if tenant is None:
        raise SystemExit(f"No existe ningún tenant con slug '{args.tenant}'")
    with scoped_to(db, tenant.id):
        _run(db, args)
    db.close()


def _run(db, args) -> None:
    token = get_tenant_secrets(db.info["tenant_id"]).discogs_token
    has_token = bool(token)
    if not has_token:
        print("⚠️  Sense DISCOGS_TOKEN: límit de 25 req/min. Afegeix el token a .env per anar més ràpid.")
        print("   https://www.discogs.com/settings/developers → 'Generate new token'")
        print()

    default_rate = 55 if has_token else 20
    rate = args.calls_per_min or default_rate
    calls_per_release = 2 if args.quality == "full" else 1
    rl = RateLimiter(rate)

    total_releases, amb_img = stats(db)
    sense_img = total_releases - amb_img
    if args.force:
        print(f"MODE --force: reprocessant tots els releases ({total_releases})")
    else:
        print(f"Releases sense imatge: {sense_img} / {total_releases}")

    if not args.force and sense_img == 0:
        print("Tots els releases ja tenen imatge. Usa --force per actualitzar a full quality. ✓")
        return

    target = total_releases if args.force else sense_img
    estimated_calls = target * calls_per_release
    estimated_min = estimated_calls / rate
    print(f"Qualitat: {args.quality} | Rate: {rate} crides/min | "
          f"Estimació: {estimated_calls} crides ≈ {estimated_min:.0f} min per {target} releases")
    if args.limit:
        print(f"Limitant a {args.limit} releases.")
    if args.dry_run:
        print("MODE DRY-RUN: no es guardarà res.")
    print()

    # Releases a processar
    stmt = select(Release).outerjoin(RecordProduct).order_by(RecordProduct.discogs_release_id.desc().nullslast())
    if not args.force:
        stmt = stmt.where(Release.image_url.is_(None))
    releases = db.scalars(stmt).all()
    if args.limit:
        releases = releases[: args.limit]

    ok = skip = errors = 0
    start = time.monotonic()

    with httpx.Client(base_url=BASE, headers=_headers(token), timeout=20) as client:
        for i, release in enumerate(releases, start=1):
            prefix = f"[{i}/{len(releases)}] {release.artista[:30]} — {release.title[:30]}"

            # --- Pas 1: assegurar que tenim discogs_release_id ---
            imagen_url = None
            discogs_release_id = release.discogs_release_id

            if discogs_release_id is None:
                # Busquem via el listing del marketplace (codi_discogs d'un ítem)
                codi = get_item_codi(db, release.id)
                if codi is None:
                    print(f"  {prefix} → sense codi_discogs, saltant")
                    skip += 1
                    continue
                try:
                    info = fetch_listing(client, rl, codi)
                except Exception as exc:
                    print(f"  {prefix} → error listing {codi}: {exc}", file=sys.stderr)
                    errors += 1
                    continue
                if info is None:
                    print(f"  {prefix} → listing {codi} no existeix a Discogs")
                    skip += 1
                    continue
                discogs_release_id = info.get("discogs_release_id")
                imagen_url = info.get("imagen_url")  # thumbnail de l'API del marketplace

            # --- Pas 2: obtenir la imatge del release ---
            # Sempre que tenim discogs_release_id i NO tenim imatge thumbnail (mode thumbnail)
            # o sempre en mode full.
            if discogs_release_id and (args.quality == "full" or not imagen_url):
                try:
                    url = fetch_release_image(client, rl, discogs_release_id)
                    if url:
                        imagen_url = url
                except Exception as exc:
                    print(f"  {prefix} → error release {discogs_release_id}: {exc}", file=sys.stderr)
                    # Continuem amb la thumbnail si en tenim del marketplace

            if not imagen_url:
                print(f"  {prefix} → sense imatge disponible")
                skip += 1
                continue

            # --- Guardar ---
            status = "dry-run" if args.dry_run else "✓"
            print(f"  {prefix} → {status}")
            if not args.dry_run:
                release.image_url = imagen_url
                if discogs_release_id:
                    release.discogs_release_id = discogs_release_id
                db.add(release)
                if i % 50 == 0:
                    db.commit()
            ok += 1

    db.commit()

    elapsed = time.monotonic() - start
    print(f"\n{'DRY-RUN ' if args.dry_run else ''}Fet en {elapsed/60:.1f} min: "
          f"{ok} imatges guardades, {skip} saltades, {errors} errors.")


if __name__ == "__main__":
    main()
