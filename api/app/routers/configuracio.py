"""Router de configuració: dades fiscals/botiga, tipus d'IVA i marges.

Tot el que és "com es comporta la botiga per defecte" viu aquí, en lloc
d'estar escampat a `.env` (`Settings`) o barrejat amb els informes de
`comptabilitat.py`.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ConfiguracioBotiga, MargeConfig, PesFormat, Seccio, TipusIva, TramEnviament
from ..schemas import (
    ConfiguracioBotigaOut, ConfiguracioBotigaPublic, ConfiguracioBotigaUpdate,
    MargeConfigIn, MargeConfigOut, MargeConfigUpdate,
    PesFormatIn, PesFormatOut, PesFormatUpdate,
    SeccioIn, SeccioOut,
    TenantSecretsStatusOut, TenantSecretsUpdateIn,
    TipusIvaIn, TipusIvaOut, TipusIvaUpdate,
    TramEnviamentIn, TramEnviamentOut, TramEnviamentUpdate,
)
from ..services.security import require_admin
from ..tenant_secrets import TenantSecrets, get_tenant_secrets, set_tenant_secret

router = APIRouter(prefix="/admin", tags=["configuracio"], dependencies=[Depends(require_admin)])
public_router = APIRouter(prefix="/config", tags=["configuracio"])


# ---------------------------------------------------------------------------
# Configuració general (una fila per tenant, ver models.py::ConfiguracioBotiga)
# ---------------------------------------------------------------------------

def _get_or_create_config(db: Session) -> ConfiguracioBotiga:
    # select() en vez de db.get(): la fila ya no tiene un id fijo (era id=1
    # antes de ser multi-tenant), el filtro automático de tenant (ver
    # app/tenancy.py) la resuelve por tenant_id.
    config = db.scalar(select(ConfiguracioBotiga))
    if config is None:
        config = ConfiguracioBotiga(fiscal_name="", address="")
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
def get_configuracio_publica(request: Request, db: Session = Depends(get_db)):
    config = db.scalar(select(ConfiguracioBotiga))
    if config is None:
        raise HTTPException(404, "Configuració no trobada")
    # `vertical`/`nombre` viven en Tenant, no en ConfiguracioBotiga — ya
    # disponibles en request.state.tenant (get_db lo resuelve por Host),
    # sin consulta extra. No se puede hacer
    # model_validate(config).model_copy(update=...): el primer paso ya
    # falla, porque esos son campos obligatorios del schema que `config`
    # (fila de ConfiguracioBotiga) no tiene.
    tenant_fields = {"vertical", "nombre", "slug"}
    data = {f: getattr(config, f) for f in ConfiguracioBotigaPublic.model_fields if f not in tenant_fields}
    data["vertical"] = request.state.tenant.vertical_id
    data["nombre"] = request.state.tenant.nombre
    data["slug"] = request.state.tenant.slug
    return ConfiguracioBotigaPublic(**data)


# ---------------------------------------------------------------------------
# Tipus d'IVA
# ---------------------------------------------------------------------------

def _aplicar_defectes_exclusius(tipus: TipusIva, db: Session, payload: dict) -> None:
    """Només un tipus actiu pot ser el per defecte de nou / de segona mà a la vegada."""
    if payload.get("default_new"):
        db.execute(
            update(TipusIva).where(TipusIva.id != tipus.id).values(default_new=False)
        )
    if payload.get("default_used"):
        db.execute(
            update(TipusIva).where(TipusIva.id != tipus.id).values(default_used=False)
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
    stmt = select(TipusIva).order_by(TipusIva.active.desc(), TipusIva.percentage.desc())
    if nomes_actius:
        stmt = stmt.where(TipusIva.active == True)
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
    if payload.get("default_new"):
        db.execute(
            update(MargeConfig).where(MargeConfig.id != marge.id).values(default_new=False)
        )
    if payload.get("default_used"):
        db.execute(
            update(MargeConfig).where(MargeConfig.id != marge.id).values(default_used=False)
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
    stmt = select(MargeConfig).order_by(MargeConfig.active.desc(), MargeConfig.percentage.desc())
    if nomes_actius:
        stmt = stmt.where(MargeConfig.active == True)
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
    stmt = select(TramEnviament).order_by(TramEnviament.country.asc(), TramEnviament.max_weight_g.asc())
    if nomes_actius:
        stmt = stmt.where(TramEnviament.active == True)
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
# Alternatiu... — veure Release.section_id / mode "remena" del catàleg)
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
    return db.scalars(select(Seccio).order_by(Seccio.position, Seccio.id)).all()


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


# ---------------------------------------------------------------------------
# Secretos del tenant (Redsys/Discogs/Spotify) — Fase 5: el propio tenant
# los gestiona, el superadmin ya solo tiene lectura de estado (ver
# routers/superadmin.py::get_tenant_secrets_status). Igual que allí, nunca
# se devuelve el valor en sí, solo si está configurado o no.
# ---------------------------------------------------------------------------

@router.get("/secrets", response_model=TenantSecretsStatusOut)
def get_secrets_status(request: Request):
    secrets_: TenantSecrets = get_tenant_secrets(request.state.tenant.id)
    return TenantSecretsStatusOut(**{k: bool(v) for k, v in secrets_.model_dump().items()})


@router.post("/secrets", response_model=TenantSecretsStatusOut)
def update_secrets(payload: TenantSecretsUpdateIn, request: Request):
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(422, "No s'ha indicat cap camp a desar")
    secrets_ = set_tenant_secret(request.state.tenant.id, **fields)
    return TenantSecretsStatusOut(**{k: bool(v) for k, v in secrets_.model_dump().items()})
