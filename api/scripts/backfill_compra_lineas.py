"""Reconstrueix `CompraLinea` de recepcions antigues i repara el cost diluït.

Abans de `compra_lineas`, el PDF de recepció llegia el `Item` agregat (stock
acumulat i cost mitjà), de manera que mostrava unitats i cost errats, i el cost
mitjà es calculava tractant un cost previ desconegut com a 0 € (diluint-lo).

Per a cada Compra de comanda sense línies:
  - segona mà: cada Item és una còpia exacta (quantitat 1, cost, preu, grading).
  - nou: quantitat = `received_quantity` de la línia de comanda, cost = el de la
    línia de comanda, PVP = el de l'Item. NOMÉS es considera fiable si la comanda
    té una única recepció i la suma quantitat×cost quadra amb `Compra.total_cost`
    (la dada exacta que es va fixar en rebre). Si no quadra, no es toca i s'avisa.

Després, per a cada línia nou amb estoc previ (Item.quantity > unitats rebudes) el
cost del qual té la signatura de la diluïció (= cost × rebudes / total), es
restaura el cost de la recepció.

Per defecte NO escriu res (simulació). Amb --apply fa els canvis.

    python -m scripts.backfill_compra_lineas --tenant <slug> [--comanda 2026-000049]
    python -m scripts.backfill_compra_lineas --tenant <slug> [--comanda ...] --apply
"""

import argparse
from decimal import Decimal

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Comanda, Compra, CompraLinea, CondicionItem, Item, Tenant
from app.tenancy import scoped_to

CENT = Decimal("0.01")


def run(db, tenant_id, comanda_num: str | None, apply: bool) -> dict:
    resum = {"reconstruides": 0, "no_quadra": 0, "ambigues": 0, "cost_reparat": 0}
    with scoped_to(db, tenant_id):
        stmt = (
            select(Compra)
            .join(Comanda, Comanda.id == Compra.comanda_id)
            .where(~select(CompraLinea.id).where(CompraLinea.compra_id == Compra.id).exists())
            .order_by(Compra.date)
        )
        if comanda_num:
            stmt = stmt.where(Comanda.order_number == comanda_num)
        for compra in db.scalars(stmt).all():
            comanda = compra.comanda
            etiqueta = f"{comanda.order_number} ({compra.date:%d/%m/%Y})"
            n_compres = db.scalar(select(func.count()).select_from(Compra).where(Compra.comanda_id == comanda.id))

            noves: list[CompraLinea] = []
            reparacions: list[tuple[Item, Decimal, str]] = []

            for item in compra.items:
                if item.condition != CondicionItem.nou:
                    noves.append(CompraLinea(
                        compra_id=compra.id, item_id=item.id, release_id=item.release_id,
                        condition=item.condition.value, quantity=1, acquisition_cost=item.acquisition_cost,
                        price=item.price, estado_disco=item.estado_disco,
                    ))

            nou_ok = n_compres == 1
            if not nou_ok and any(i.condition == CondicionItem.nou for i in compra.items):
                resum["ambigues"] += 1
                print(f"  [AMBIGUA, no es toca] {etiqueta}: la comanda té {n_compres} recepcions")
                continue

            for linea in comanda.lineas:
                if linea.received_quantity <= 0:
                    continue
                item = db.scalar(select(Item).where(
                    Item.release_id == linea.release_id, Item.condition == CondicionItem.nou))
                if item is None or item.compra_id != compra.id:
                    continue  # és una línia segona mà (ja reconstruïda) o l'estoc ja ha passat a una altra compra
                if linea.estimated_unit_price is None:
                    continue
                noves.append(CompraLinea(
                    compra_id=compra.id, item_id=item.id, release_id=item.release_id, condition="nou",
                    quantity=linea.received_quantity, acquisition_cost=linea.estimated_unit_price,
                    price=item.price,
                ))
                if item.quantity > linea.received_quantity and item.acquisition_cost is not None:
                    diluit = (linea.estimated_unit_price * linea.received_quantity / item.quantity).quantize(CENT)
                    if abs(item.acquisition_cost - diluit) <= CENT:
                        reparacions.append((item, linea.estimated_unit_price,
                                            f"{item.acquisition_cost} -> {linea.estimated_unit_price}"))

            suma = sum(((l.acquisition_cost or Decimal("0")) * l.quantity for l in noves), Decimal("0"))
            if compra.total_cost is None or abs(suma - compra.total_cost) > CENT:
                resum["no_quadra"] += 1
                print(f"  [NO QUADRA, no es toca] {etiqueta}: reconstruït {suma} vs total_cost {compra.total_cost}")
                continue

            resum["reconstruides"] += 1
            print(f"  [{'reconstruïda' if apply else 'reconstruiria'}] {etiqueta}: "
                  f"{len(noves)} línies, total {suma} € (quadra amb la recepció)")
            for item, cost, canvi in reparacions:
                resum["cost_reparat"] += 1
                print(f"      cost {'reparat' if apply else 'es repararia'}: "
                      f"{item.release.artista} - {item.release.title}: {canvi}")
                if apply:
                    item.acquisition_cost = cost
            if apply:
                db.add_all(noves)

        if apply:
            db.commit()
        else:
            db.rollback()
    return resum



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--comanda", help="número de comanda (p. ex. 2026-000049); per defecte, totes")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    tenant = db.scalar(select(Tenant).where(Tenant.slug == args.tenant))
    if tenant is None:
        raise SystemExit(f"No existe ningún tenant con slug '{args.tenant}'")

    resum = run(db, tenant.id, args.comanda, args.apply)
    ap = args.apply
    print(f"\n{resum['reconstruides']} recepcions {'reconstruïdes' if ap else 'es reconstruiran'} · "
          f"{resum['cost_reparat']} costos {'reparats' if ap else 'es repararan'} · "
          f"{resum['no_quadra']} no quadren · {resum['ambigues']} ambígues")
    if not ap:
        print("Simulació: no s'ha escrit res. Afegeix --apply per aplicar-ho.")


if __name__ == "__main__":
    main()
