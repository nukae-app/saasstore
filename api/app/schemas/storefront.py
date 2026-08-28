from datetime import datetime

from pydantic import BaseModel, field_validator

from ..blocks.registry import BLOCK_REGISTRY


class HomeBlockOut(BaseModel):
    id: int
    block_type: str
    position: int
    enabled: bool
    props: dict
    updated_at: datetime

    model_config = {"from_attributes": True}


class HomeBlockPublicOut(BaseModel):
    """Lectura pública (/config/public/home-blocks) — sin id/updated_at,
    solo lo que [locale]/page.jsx necesita para renderizar."""
    id: int
    block_type: str
    props: dict

    model_config = {"from_attributes": True}


class HomeBlockCreateIn(BaseModel):
    block_type: str
    props: dict = {}

    @field_validator("block_type")
    @classmethod
    def _known_block_type(cls, v: str) -> str:
        if v not in BLOCK_REGISTRY:
            # ValueError de Pydantic aquí es aceptable (a diferencia del
            # slug de tenant/tema): esto no es un formulario de admin con
            # texto libre, el frontend solo manda valores que ya salen del
            # propio registro, nunca tecleados a mano.
            raise ValueError(f"Tipus de bloc desconegut: '{v}'")
        return v


class HomeBlockUpdateIn(BaseModel):
    props: dict | None = None
    enabled: bool | None = None


class HomeBlockPositionIn(BaseModel):
    id: int
    position: int


class HomeBlockReorderIn(BaseModel):
    order: list[HomeBlockPositionIn]
