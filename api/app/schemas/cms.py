import uuid
from datetime import date, datetime

from pydantic import BaseModel


class PostOut(BaseModel):
    slug: str
    title: str
    content: str
    language: str
    published_at: datetime | None

    model_config = {"from_attributes": True}


class EventOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    date: datetime
    location: str
    link: str | None

    model_config = {"from_attributes": True}


# --- Comptabilitat: Tipus d'IVA ---
