"""Reconcilia la BD amb l'inventari REAL del Marketplace de Discogs (compte
venedor autenticat pel DISCOGS_TOKEN). Només fa lectura (GET) a Discogs:
mai crea, edita ni elimina cap listing — per a això ja hi ha
`POST /admin/discogs/sync/items/{id}/push` i el botó equivalent d'eliminar.

Pensat per posar-se al dia quan la BD s'ha quedat desincronitzada (p. ex.
dies sense poder provar amb el token de producció) sense arriscar-se a
tocar res del compte real de Discogs.

Comportament (mateixa filosofia que app/services/catalog_sync.py, però la
font és directament l'API en lloc del CSV del sheet):
  - Listing "For Sale" a Discogs que no existeix a la BD (per codi_discogs):
    - segona_ma -> es crea sempre un Item nou (cada còpia és única).
    - nou (stock agregat) -> si ja hi ha una línia `nou` per aquest release,
      se li suma 1 a `cantidad` (i se li assigna aquest codi_discogs NOMÉS
      si encara no en tenia cap — "stock virtual de 1", veure
      services/discogs_sync.py). Si n'hi ha dues listings actives per al
      mateix release (cas rar, herència d'abans d'aquesta funcionalitat),
      la segona només suma cantidad; el seu codi_discogs no es guarda
      enlloc (no hi ha lloc per a un segon), es tracta com a marge de
      millora manual des de l'admin.
    - Si cal, es crea el Release consultant /releases/{id}.
  - Listing que ja existeix a la BD -> el preu es sincronitza amb el que
    digui Discogs ara mateix (condició/grading NO es toca, es manté la
    que ja hi havia). Discogs mana en preu; per canviar-lo cal fer-ho allà.
  - Item a la BD amb status=disponible i codi_discogs que ja NO és
    "For Sale" a Discogs:
    - segona_ma -> es marca com a `retirado` (venut o retirat allà).
    - nou -> es descomptem 1 unitat de `cantidad` i es buida `codi_discogs`
      (aquest script mai crea ni elimina listings, és només lectura de
      Discogs — si encara queda stock, la línia es queda "Pendent" fins que
      algú premi "Pujar" a mà o torni a passar per aquí en una altra
      execució i Discogs mostri un listing nou per a aquest release).
  - Mai toca items en estat reservado/vendido/retirado.

Pas previ (herència d'abans del stock agregat): consolida en una sola línia
els releases que ja tenen més d'una fila `nou` a la BD (venien del model
antic, una fila per unitat). Sobreviu la de `fecha_entrada` més antiga
(mateix criteri d'antiguitat que la resta de l'app); s'hi suma `cantidad` i
`coste_adquisicion` (mitjana ponderada) de la resta abans d'esborrar-les.
Si la que sobreviu no tenia codi_discogs però alguna de les altres sí,
n'hereta un; si diverses en tenien, la resta queden sense el seu
codi_discogs rastrejat aquí (segueixen actives a Discogs igualment, només
deixem de vincular-les a un item local — marge de millora manual).
Només consolida releases sense cap referència externa (OrderItem,
VentaExterna, CartItem, PeticionCliente, Assignacio, SolicitudCompraLinea,
Devolucions, StockHold) a cap de les files a esborrar — si n'hi ha, es
deixa el release tal qual i es reporta per revisar-lo a mà.

Ús:
  docker compose exec api python -m scripts.sync_discogs_inventory --tenant recordstore
  docker compose exec api python -m scripts.sync_discogs_inventory --tenant recordstore --dry-run
  docker compose exec api python -m scripts.sync_discogs_inventory --tenant recordstore --limit 50

Fase 2 (secretos por tenant, ver app/tenant_secrets.py): `--tenant` es
obligatorio — este script abre su propia sesión sin tenant por defecto, y
`Item`/`Release` son TenantScoped, así que cualquier INSERT sin tenant_id
revienta con IntegrityError a media ejecución.
"""

import argparse
import sys
import time
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import (
    Assignacio, CartItem, CondicionItem, DevolucionCompra, DevolucionVenta, Item, ItemStatus,
    OrderItem, PeticionCliente, RecordProduct, RecordStockDetail, Release, SolicitudCompraLinea,
    StockHold, Tenant, VentaExterna,
)
from app.services import discogs
from app.services.catalog_sync import clean, derive_condicion
from app.tenancy import scoped_to
from app.tenant_secrets import get_tenant_secrets


def _tiene_dependientes(db, item_id) -> bool:
    """Cualquier referencia externa a este item_id (ver docstring del módulo):
    si hay alguna, no se consolida ese release automáticamente."""
    checks = (
        (OrderItem, OrderItem.item_id), (VentaExterna, VentaExterna.item_id),
        (CartItem, CartItem.item_id), (PeticionCliente, PeticionCliente.item_id),
        (Assignacio, Assignacio.item_id), (SolicitudCompraLinea, SolicitudCompraLinea.item_resuelto_id),
        (DevolucionVenta, DevolucionVenta.item_id), (DevolucionCompra, DevolucionCompra.item_id),
        (StockHold, StockHold.item_id),
    )
    return any(
        db.scalar(select(func.count()).select_from(model).where(col == item_id))
        for model, col in checks
    )


def _consolidar_duplicados_nou(db, dry_run: bool) -> int:
    """Fusiona en una sola fila los releases que ya tienen más de una línea
    `nou` (herencia del modelo anterior, una fila por unidad). Ver docstring
    del módulo para el criterio exacto. Devuelve cuántos releases se han
    consolidado."""
    grupos = db.execute(
        select(Item.release_id, func.count(Item.id))
        .where(Item.condition == CondicionItem.nou)
        .group_by(Item.release_id)
        .having(func.count(Item.id) > 1)
    ).all()

    consolidados = 0
    for release_id, _ in grupos:
        items = list(db.scalars(
            select(Item).where(Item.release_id == release_id, Item.condition == CondicionItem.nou)
        ))
        if any(_tiene_dependientes(db, it.id) for it in items):
            release = db.get(Release, release_id)
            print(
                f"  [omitido] {release.artista} - {release.title}: alguna de las "
                f"{len(items)} líneas tiene referencias externas, revisar a mano.",
                file=sys.stderr,
            )
            continue

        items.sort(key=lambda it: it.entry_date or it.created_at)
        superviviente, *resto = items

        cantidad_total = sum(it.quantity for it in items)
        coste_base = superviviente.acquisition_cost
        cantidad_acumulada = superviviente.quantity
        for it in resto:
            if it.acquisition_cost is not None:
                coste_previo = coste_base if coste_base is not None else it.acquisition_cost
                coste_base = (
                    (cantidad_acumulada * coste_previo + it.quantity * it.acquisition_cost)
                    / (cantidad_acumulada + it.quantity)
                )
            cantidad_acumulada += it.quantity
            if superviviente.codi_discogs is None and it.codi_discogs is not None:
                # Primero se vacía aquí y se aplica el flush: si no, la UPDATE
                # del superviviente y el DELETE de `it` pueden ejecutarse en
                # un orden que deje un instante con dos filas con el mismo
                # codi_discogs, violando la UNIQUE.
                codi = it.codi_discogs
                it.codi_discogs = None
                db.flush()
                superviviente.codi_discogs = codi

        superviviente.quantity = cantidad_total
        superviviente.acquisition_cost = coste_base

        release = db.get(Release, release_id)
        print(
            f"  {release.artista} - {release.title}: {len(items)} líneas -> 1 "
            f"(cantidad={cantidad_total}, codi_discogs={superviviente.codi_discogs})"
        )
        for it in resto:
            db.delete(it)
        consolidados += 1

    if not dry_run and consolidados:
        db.commit()
    return consolidados


def _parse_posted(value: str | None) -> datetime | None:
    """Data en què el listing es va publicar al Marketplace de Discogs (ISO 8601).
    Per a stock que ja hi era abans d'aquesta app (no ve de cap Compra), és la
    millor aproximació disponible a la data d'entrada real al magatzem."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _fetch_username(token: str | None) -> str:
    """El token identifica un únic compte; en traiem el username via /oauth/identity
    (mateix token, no cal cap variable d'entorn nova)."""
    discogs._throttle()
    with discogs._client(token) as c:
        r = c.get("/oauth/identity")
        r.raise_for_status()
        return r.json()["username"]


def _fetch_inventory(token: str | None, username: str, limit: int = 0) -> list[dict]:
    """Totes les listings 'For Sale' del compte venedor (paginat)."""
    listings: list[dict] = []
    page = 1
    while True:
        discogs._throttle()
        with discogs._client(token) as c:
            r = c.get(
                f"/users/{username}/inventory",
                params={"status": "For Sale", "per_page": 100, "page": page},
            )
            r.raise_for_status()
            data = r.json()
        listings.extend(data.get("listings", []))
        if limit and len(listings) >= limit:
            return listings[:limit]
        pagination = data.get("pagination", {})
        if page >= pagination.get("pages", 1):
            break
        page += 1
    return listings


def _find_or_create_release(db, token: str | None, discogs_release_id: int, description: str) -> Release:
    release = db.scalar(
        select(Release).join(RecordProduct).where(RecordProduct.discogs_release_id == discogs_release_id)
    )
    if release:
        return release

    artista, titulo = None, description
    if " - " in description:
        artista, titulo = description.split(" - ", 1)
        artista, titulo = artista.strip(), titulo.strip()

    if artista:
        release = db.scalar(
            select(Release).join(RecordProduct).where(RecordProduct.artista.ilike(artista), Release.title.ilike(titulo))
        )
        if release:
            # Ja existia (alta manual anterior, p. ex.): el vinculem a Discogs.
            release.discogs_release_id = discogs_release_id
            return release

    # Release nou de veritat: consultem dades completes (sello, format, any...).
    # Reintenta en 429 (rate limit) en comptes de saltar-se el disc directament:
    # amb milers de listings és fàcil topar-hi encara respectant el throttle.
    data = None
    for attempt in range(4):
        try:
            data = discogs.get_release(token, discogs_release_id)
            break
        except Exception as exc:
            if "429" in str(exc) and attempt < 3:
                wait = 65 * (attempt + 1)
                print(f"  429 rate limit (release {discogs_release_id}) — esperant {wait}s...", flush=True)
                time.sleep(wait)
            else:
                raise
    data = data or {}
    release = Release(
        artista=data.get("artista") or artista or "Desconegut",
        title=data.get("titulo") or titulo,
        sello=data.get("sello"),
        referencia=data.get("referencia"),
        anio=data.get("anio"),
        genero=data.get("genero"),
        pais=data.get("pais"),
        estilos=data.get("estilos"),
        formato=data.get("formato"),
        tracklist=data.get("tracklist"),
        credits=data.get("credits"),
        ean=data.get("ean"),
        image_url=data.get("imagen_url"),
        discogs_release_id=discogs_release_id,
    )
    db.add(release)
    db.flush()
    return release


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tenant", required=True, help="Slug del tenant (ver tabla tenants)")
    parser.add_argument("--dry-run", action="store_true", help="simula sense guardar res a la BD")
    parser.add_argument("--limit", type=int, default=0, help="processa només N listings (per provar)")
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
    print("Consolidant línies `nou` duplicades (herència d'abans del stock agregat)...", flush=True)
    consolidados = _consolidar_duplicados_nou(db, args.dry_run)
    print(f"  {consolidados} releases consolidats.\n", flush=True)

    username = _fetch_username(token)
    print(f"Compte Discogs autenticat: {username}", flush=True)

    listings = _fetch_inventory(token, username, args.limit)
    print(f"Listings 'For Sale' a Discogs: {len(listings)}", flush=True)

    codis_discogs = {int(l["id"]) for l in listings}

    # Items locals ja vinculats a un listing (per detectar els que ja no hi són).
    items_locals = {
        i.codi_discogs: i
        for i in db.scalars(
            select(Item).join(RecordStockDetail, RecordStockDetail.item_id == Item.id)
            .where(RecordStockDetail.codi_discogs.isnot(None))
        ).all()
    }
    # Línies `nou` ja existents per release_id, per poder-hi sumar quan
    # trobem un listing "For Sale" del mateix release que encara no
    # rastrejàvem (recentment consolidades, o donades d'alta a mà/ERP).
    nou_por_release = {
        i.release_id: i
        for i in db.scalars(select(Item).where(Item.condition == CondicionItem.nou)).all()
    }

    creados = actualizados = sumados = errores = 0
    for i, listing in enumerate(listings, 1):
        codi = int(listing["id"])

        try:
            precio_raw = listing.get("price", {}).get("value")
            if precio_raw is None:
                errores += 1
                print(f"  listing {codi}: sense preu, es salta", file=sys.stderr)
                continue
            precio = Decimal(str(precio_raw))

            item_existent = items_locals.get(codi)
            if item_existent:
                # Ja el tenim: mantenim condició tal com estava, però el preu
                # sí es manté sincronitzat amb el que digui Discogs ara mateix.
                canviat = False
                if item_existent.price != precio:
                    item_existent.price = precio
                    canviat = True
                # Stock anterior a aquesta app (mai va passar per una Compra):
                # aprofitem per omplir fecha_entrada amb el "posted" de Discogs
                # si encara no en teníem cap.
                if item_existent.entry_date is None:
                    posted = _parse_posted(listing.get("posted"))
                    if posted is not None:
                        item_existent.entry_date = posted
                        canviat = True
                if canviat:
                    actualizados += 1
                continue

            rel_info = listing.get("release") or {}
            release = _find_or_create_release(db, token, rel_info["id"], rel_info.get("description", ""))

            estado_disco = clean(listing.get("condition"))
            condicion = derive_condicion(estado_disco)

            if condicion == CondicionItem.nou:
                agregado = nou_por_release.get(release.id)
                if agregado is not None:
                    agregado.quantity += 1
                    if agregado.price != precio:
                        agregado.price = precio
                    if agregado.codi_discogs is None:
                        agregado.codi_discogs = codi
                        items_locals[codi] = agregado
                    sumados += 1
                else:
                    nuevo = Item(
                        release_id=release.id,
                        codi_discogs=codi,
                        price=precio,
                        condition=condicion,
                        status=ItemStatus.disponible,
                        entry_date=_parse_posted(listing.get("posted")),
                    )
                    db.add(nuevo)
                    db.flush()
                    nou_por_release[release.id] = nuevo
                    items_locals[codi] = nuevo
                    creados += 1
            else:
                db.add(
                    Item(
                        release_id=release.id,
                        codi_discogs=codi,
                        price=precio,
                        condition=condicion,
                        estado_disco=estado_disco,
                        estado_funda=clean(listing.get("sleeve_condition")),
                        status=ItemStatus.disponible,
                        entry_date=_parse_posted(listing.get("posted")),
                    )
                )
                creados += 1

            if i % 25 == 0:
                print(f"  [{i}/{len(listings)}] ...", flush=True)
            if not args.dry_run and i % 50 == 0:
                db.commit()  # progrés parcial: no perdre-ho tot si el procés es talla
        except Exception as exc:
            errores += 1
            print(f"  listing {codi}: error ({exc}), es salta", file=sys.stderr, flush=True)

    # Retirar: disponibles localment amb codi_discogs que ja NO és "For Sale".
    # Per a nou, no es retira la línia sencera (representaria perdre les
    # altres unitats que encara hi ha): es descompta 1 unitat i es buida
    # el codi_discogs (script de només lectura: mai republica ell mateix).
    retirados = 0
    for codi, item in items_locals.items():
        if codi in codis_discogs or item.status != ItemStatus.disponible:
            continue
        if item.condition == CondicionItem.nou:
            item.quantity = max(0, item.quantity - 1)
            item.codi_discogs = None
        else:
            item.status = ItemStatus.retirado
            item.reserved_until = None
            item.reserved_by_cart_id = None
        retirados += 1

    if args.dry_run:
        db.rollback()
        print(
            f"\nDRY-RUN (res guardat): {creados} es crearien, {sumados} sumarien a una línia nou existent, "
            f"{actualizados} es canviarien (preu/fecha_entrada), {retirados} es retirarien/descomptarien, "
            f"{errores} errors."
        )
    else:
        db.commit()
        print(
            f"\nFet: {creados} ejemplars creats, {sumados} sumats a línies nou existents, "
            f"{actualizados} actualitzats (preu/fecha_entrada), {retirados} retirats/descomptats, "
            f"{errores} errors."
        )


if __name__ == "__main__":
    main()
