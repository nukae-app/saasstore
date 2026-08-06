"""Router de configuració: dades fiscals/botiga, tipus d'IVA i marges.

Tot el que és "com es comporta la botiga per defecte" viu aquí, en lloc
d'estar escampat a `.env` (`Settings`) o barrejat amb els informes de
`comptabilitat.py`.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ConfiguracioBotiga, MargeConfig, PesFormat, Seccio, TipusIva, TramEnviament
from ..schemas import (
    ConfiguracioBotigaOut, ConfiguracioBotigaPublic, ConfiguracioBotigaUpdate,
    MargeConfigIn, MargeConfigOut, MargeConfigUpdate,
    PesFormatIn, PesFormatOut, PesFormatUpdate,
    SeccioIn, SeccioOut,
    TipusIvaIn, TipusIvaOut, TipusIvaUpdate,
    TramEnviamentIn, TramEnviamentOut, TramEnviamentUpdate,
)
from ..services.security import require_admin

router = APIRouter(prefix="/admin", tags=["configuracio"], dependencies=[Depends(require_admin)])
public_router = APIRouter(prefix="/config", tags=["configuracio"])


# ---------------------------------------------------------------------------
# Configuració general (fila singleton id=1)
# ---------------------------------------------------------------------------

def _get_or_create_config(db: Session) -> ConfiguracioBotiga:
    config = db.get(ConfiguracioBotiga, 1)
    if config is None:
        config = ConfiguracioBotiga(id=1, nom_fiscal="", adreca="")
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.get("/configuracio", response_model=ConfiguracioBotigaOut)
def get_configuracio(db: Session = Depends(get_db)):
    return _get_or_create_config(db)


@router.patch("/configuracio", response_model=ConfiguracioBotigaOut)
def update_configuracio(payload: ConfiguracioBotigaUpdate, db: Session = Depends(get_db)):
    config = _get_or_create_config(db)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(config, k, v)
    db.commit()
    db.refresh(config)
    return config


@public_router.get("/public", response_model=ConfiguracioBotigaPublic)
def get_configuracio_publica(db: Session = Depends(get_db)):
    config = db.get(ConfiguracioBotiga, 1)
    if config is None:
        raise HTTPException(404, "Configuració no trobada")
    return config


# ---------------------------------------------------------------------------
# Tipus d'IVA
# ---------------------------------------------------------------------------

def _aplicar_defectes_exclusius(tipus: TipusIva, db: Session, payload: dict) -> None:
    """Només un tipus actiu pot ser el per defecte de nou / de segona mà a la vegada."""
    if payload.get("per_defecte_nou"):
        db.execute(
            update(TipusIva).where(TipusIva.id != tipus.id).values(per_defecte_nou=False)
        )
    if payload.get("per_defecte_segona_ma"):
        db.execute(
            update(TipusIva).where(TipusIva.id != tipus.id).values(per_defecte_segona_ma=False)
        )


@router.post("/tipus-iva", status_code=201, response_model=TipusIvaOut)
def create_tipus_iva(payload: TipusIvaIn, db: Session = Depends(get_db)):
    tipus = TipusIva(**payload.model_dump())
    db.add(tipus)
    db.flush()
    _aplicar_defectes_exclusius(tipus, db, payload.model_dump())
    db.commit()
    db.refresh(tipus)
    return tipus


@router.get("/tipus-iva", response_model=list[TipusIvaOut])
def list_tipus_iva(nomes_actius: bool = False, db: Session = Depends(get_db)):
    stmt = select(TipusIva).order_by(TipusIva.actiu.desc(), TipusIva.percentatge.desc())
    if nomes_actius:
        stmt = stmt.where(TipusIva.actiu == True)
    return db.scalars(stmt).all()


@router.patch("/tipus-iva/{tipus_id}", response_model=TipusIvaOut)
def update_tipus_iva(tipus_id: int, payload: TipusIvaUpdate, db: Session = Depends(get_db)):
    tipus = db.get(TipusIva, tipus_id)
    if tipus is None:
        raise HTTPException(404, "Tipus d'IVA no trobat")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(tipus, k, v)
    _aplicar_defectes_exclusius(tipus, db, data)
    db.commit()
    db.refresh(tipus)
    return tipus


# ---------------------------------------------------------------------------
# Marges (suggeriment de preu a la recepció, veure erp.py recibir_comanda)
# ---------------------------------------------------------------------------

def _aplicar_defectes_exclusius_marge(marge: MargeConfig, db: Session, payload: dict) -> None:
    """Només un marge actiu pot ser el per defecte de nou / de segona mà a la vegada."""
    if payload.get("per_defecte_nou"):
        db.execute(
            update(MargeConfig).where(MargeConfig.id != marge.id).values(per_defecte_nou=False)
        )
    if payload.get("per_defecte_segona_ma"):
        db.execute(
            update(MargeConfig).where(MargeConfig.id != marge.id).values(per_defecte_segona_ma=False)
        )


@router.post("/marges", status_code=201, response_model=MargeConfigOut)
def create_marge(payload: MargeConfigIn, db: Session = Depends(get_db)):
    marge = MargeConfig(**payload.model_dump())
    db.add(marge)
    db.flush()
    _aplicar_defectes_exclusius_marge(marge, db, payload.model_dump())
    db.commit()
    db.refresh(marge)
    return marge


@router.get("/marges", response_model=list[MargeConfigOut])
def list_marges(nomes_actius: bool = False, db: Session = Depends(get_db)):
    stmt = select(MargeConfig).order_by(MargeConfig.actiu.desc(), MargeConfig.percentatge.desc())
    if nomes_actius:
        stmt = stmt.where(MargeConfig.actiu == True)
    return db.scalars(stmt).all()


@router.patch("/marges/{marge_id}", response_model=MargeConfigOut)
def update_marge(marge_id: int, payload: MargeConfigUpdate, db: Session = Depends(get_db)):
    marge = db.get(MargeConfig, marge_id)
    if marge is None:
        raise HTTPException(404, "Marge no trobat")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(marge, k, v)
    _aplicar_defectes_exclusius_marge(marge, db, data)
    db.commit()
    db.refresh(marge)
    return marge


# ---------------------------------------------------------------------------
# Trams d'enviament (tarifa pròpia per pes i zona nacional/internacional,
# veure services/enviament.py)
# ---------------------------------------------------------------------------

@router.post("/trams-enviament", status_code=201, response_model=TramEnviamentOut)
def create_tram_enviament(payload: TramEnviamentIn, db: Session = Depends(get_db)):
    tram = TramEnviament(**payload.model_dump())
    db.add(tram)
    db.commit()
    db.refresh(tram)
    return tram


@router.get("/trams-enviament", response_model=list[TramEnviamentOut])
def list_trams_enviament(nomes_actius: bool = False, db: Session = Depends(get_db)):
    stmt = select(TramEnviament).order_by(TramEnviament.pais.asc(), TramEnviament.pes_maxim_g.asc())
    if nomes_actius:
        stmt = stmt.where(TramEnviament.actiu == True)
    return db.scalars(stmt).all()


@router.patch("/trams-enviament/{tram_id}", response_model=TramEnviamentOut)
def update_tram_enviament(tram_id: int, payload: TramEnviamentUpdate, db: Session = Depends(get_db)):
    tram = db.get(TramEnviament, tram_id)
    if tram is None:
        raise HTTPException(404, "Tram d'enviament no trobat")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(tram, k, v)
    db.commit()
    db.refresh(tram)
    return tram


@router.delete("/trams-enviament/{tram_id}", status_code=204)
def delete_tram_enviament(tram_id: int, db: Session = Depends(get_db)):
    tram = db.get(TramEnviament, tram_id)
    if tram is None:
        raise HTTPException(404, "Tram d'enviament no trobat")
    db.delete(tram)
    db.commit()


# ---------------------------------------------------------------------------
# Pes per format (per defecte quan un release no té pes propi, veure
# services/enviament.py)
# ---------------------------------------------------------------------------

@router.post("/pes-format", status_code=201, response_model=PesFormatOut)
def create_pes_format(payload: PesFormatIn, db: Session = Depends(get_db)):
    if db.scalar(select(PesFormat).where(PesFormat.formato == payload.formato)) is not None:
        raise HTTPException(409, f"Ja hi ha un pes configurat per al format '{payload.formato}'")
    pes = PesFormat(**payload.model_dump())
    db.add(pes)
    db.commit()
    db.refresh(pes)
    return pes


@router.get("/pes-format", response_model=list[PesFormatOut])
def list_pes_format(db: Session = Depends(get_db)):
    return db.scalars(select(PesFormat).order_by(PesFormat.formato.asc())).all()


@router.patch("/pes-format/{pes_id}", response_model=PesFormatOut)
def update_pes_format(pes_id: int, payload: PesFormatUpdate, db: Session = Depends(get_db)):
    pes = db.get(PesFormat, pes_id)
    if pes is None:
        raise HTTPException(404, "Pes per format no trobat")
    pes.pes_g = payload.pes_g
    db.commit()
    db.refresh(pes)
    return pes


@router.delete("/pes-format/{pes_id}", status_code=204)
def delete_pes_format(pes_id: int, db: Session = Depends(get_db)):
    pes = db.get(PesFormat, pes_id)
    if pes is None:
        raise HTTPException(404, "Pes per format no trobat")
    db.delete(pes)
    db.commit()


# ---------------------------------------------------------------------------
# Seccions (cubetes físiques de la botiga: Nacional, Internacional,
# Alternatiu... — veure Release.seccio_id / mode "remena" del catàleg)
# ---------------------------------------------------------------------------

@router.post("/seccions", status_code=201, response_model=SeccioOut)
def create_seccio(payload: SeccioIn, db: Session = Depends(get_db)):
    if db.scalar(select(Seccio).where(Seccio.slug == payload.slug)) is not None:
        raise HTTPException(409, f"Ja hi ha una secció amb el slug '{payload.slug}'")
    seccio = Seccio(**payload.model_dump())
    db.add(seccio)
    db.commit()
    db.refresh(seccio)
    return seccio


@router.get("/seccions", response_model=list[SeccioOut])
def list_seccions(db: Session = Depends(get_db)):
    return db.scalars(select(Seccio).order_by(Seccio.posicio, Seccio.id)).all()


@router.patch("/seccions/{seccio_id}", response_model=SeccioOut)
def update_seccio(seccio_id: int, payload: SeccioIn, db: Session = Depends(get_db)):
    seccio = db.get(Seccio, seccio_id)
    if seccio is None:
        raise HTTPException(404, "Secció no trobada")
    existent = db.scalar(select(Seccio).where(Seccio.slug == payload.slug, Seccio.id != seccio_id))
    if existent is not None:
        raise HTTPException(409, f"Ja hi ha una secció amb el slug '{payload.slug}'")
    for k, v in payload.model_dump().items():
        setattr(seccio, k, v)
    db.commit()
    db.refresh(seccio)
    return seccio


@router.delete("/seccions/{seccio_id}", status_code=204)
def delete_seccio(seccio_id: int, db: Session = Depends(get_db)):
    seccio = db.get(Seccio, seccio_id)
    if seccio is None:
        raise HTTPException(404, "Secció no trobada")
    db.delete(seccio)
    db.commit()
