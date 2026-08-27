from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import ConfiguracioBotiga


def require_discogs_enabled(db: Session = Depends(get_db)) -> None:
    """Interruptor de Discogs por tenant (ConfiguracioBotiga.discogs_habilitat)
    — mismo patrón que require_spotify_enabled (routers/spotify.py) pero
    resuelto por tenant en vez de global, porque Discogs solo tiene sentido
    para el vertical vinilo, no es una decisión de plataforma entera. Solo
    gatea las rutas dedicadas de Discogs (búsqueda/sync); las llamadas
    incrustadas en flujos de compra/venta ya degradan sin más si el tenant
    no tiene discogs_token configurado."""
    config = db.scalar(select(ConfiguracioBotiga))
    if not config or not config.discogs_habilitat:
        raise HTTPException(404)
