"""Càlcul del cost d'enviament a partir de la taula de trams de pes per país.

No hi ha cap API de tarifes de missatgeria en temps real (els preus són
contractuals: pes, dimensions, distància — no es publiquen ni es consulten
via API). El preu que es mostra i es cobra al checkout ve sempre d'aquí,
d'una taula pròpia (`TramEnviament`, línies de país + pes + preu) editable
des de l'admin. NO hi ha cap llista de països hardcodejada: un país és
venedor si i només si té almenys un tram actiu configurat — afegir un país
nou és cosa de l'admin (crear un tram), no requereix desplegament. L'etiquetatge
i el seguiment de l'enviament són manuals (numero_seguiment/transportista a
`Order`); no hi ha integració amb cap API de missatgeria.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Item, PesFormat, TramEnviament

# Fallback final quan ni el release ni el seu format tenen pes configurat
# (catàleg importat sense aquesta dada, o format que encara no s'ha donat
# d'alta a `PesFormat`). Aproximat a un LP senzill amb funda.
DEFAULT_PES_G = 350


class PaisNoDisponible(Exception):
    """El país de l'adreça d'enviament no té cap tram d'enviament actiu configurat."""


def normalitza_pais(pais: str | None) -> str:
    return (pais or "").strip().upper()


def paisos_disponibles(db: Session) -> list[str]:
    """Països amb almenys un tram actiu configurat, és a dir, a on es pot
    comprar amb enviament avui. Font única de veritat pel checkout (client
    i validació de backend): no hi ha cap llista separada a mantenir."""
    return sorted(set(db.scalars(
        select(TramEnviament.pais).where(TramEnviament.actiu == True)
    )))


def pes_total_g(items: list[Item], db: Session) -> int:
    """Suma el pes de totes les còpies. Per cada còpia: `Item.release.pes_g`
    si s'ha informat a mà (excepcions: box sets, vinil de 180g...), si no el
    pes per defecte del seu format (`PesFormat`, editable des de l'admin), i
    si tampoc hi ha res configurat per aquest format, `DEFAULT_PES_G`."""
    pes_per_format = {p.formato: p.pes_g for p in db.scalars(select(PesFormat))}
    return sum(
        (item.release.pes_g or pes_per_format.get(item.release.formato) or DEFAULT_PES_G)
        for item in items
    )


def compute_coste_enviament(pes_g: int, metodo_envio: str, pais: str | None, db: Session) -> Decimal:
    """Cost d'enviament segons el mètode, el país i el pes total de la comanda.

    `recogida_tienda` sempre és gratuït (no es comprova el país). Per
    `envio`, es busca el tram actiu d'aquell país més barat que cobreixi el
    pes (el de `pes_maxim_g` més petit que sigui >= pes_g). Si el pes supera
    tots els trams configurats d'aquell país, s'aplica el tram més car
    disponible del mateix país: mai es bloqueja un checkout per una tarifa
    incompleta un cop el país és venedor.

    Si el país no té CAP tram actiu, es considera que no s'hi ven i es
    llança `PaisNoDisponible` — el checkout ha de rebutjar la compra, no
    cobrar-la a 0.
    """
    if metodo_envio != "envio":
        return Decimal("0")

    pais_norm = normalitza_pais(pais)

    tram = db.scalar(
        select(TramEnviament)
        .where(TramEnviament.actiu == True, TramEnviament.pais == pais_norm, TramEnviament.pes_maxim_g >= pes_g)
        .order_by(TramEnviament.pes_maxim_g.asc())
    )
    if tram is not None:
        return tram.preu

    tram_mes_car = db.scalar(
        select(TramEnviament)
        .where(TramEnviament.actiu == True, TramEnviament.pais == pais_norm)
        .order_by(TramEnviament.pes_maxim_g.desc())
    )
    if tram_mes_car is not None:
        return tram_mes_car.preu

    raise PaisNoDisponible(f"No fem enviaments a aquest país ({pais or 'cap indicat'}).")
