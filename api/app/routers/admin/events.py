import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Event
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class EventIn(BaseModel):
    title: str
    description: str | None = None
    date: str  # ISO datetime
    location: str = ""
    link: str | None = None


class EventAdminOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    date: str
    location: str
    link: str | None
    created_at: str

    model_config = {"from_attributes": True}


@router.get("/events", response_model=list[EventAdminOut])
def admin_list_events(upcoming_only: bool = False, db: Session = Depends(get_db)):
    stmt = select(Event).order_by(Event.date.desc())
    if upcoming_only:
        stmt = stmt.where(Event.date >= datetime.now(timezone.utc))
    events = db.scalars(stmt).all()
    return [
        EventAdminOut(
            id=e.id, title=e.title, description=e.description,
            date=e.date.isoformat(), location=e.location, link=e.link,
            created_at=e.created_at.isoformat(),
        )
        for e in events
    ]


@router.post("/events", status_code=201, response_model=EventAdminOut)
def admin_create_event(payload: EventIn, db: Session = Depends(get_db)):
    event = Event(
        title=payload.title,
        description=payload.description,
        date=datetime.fromisoformat(payload.date),
        location=payload.location,
        link=payload.link,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return EventAdminOut(
        id=event.id, title=event.title, description=event.description,
        date=event.date.isoformat(), location=event.location, link=event.link,
        created_at=event.created_at.isoformat(),
    )


@router.put("/events/{event_id}", response_model=EventAdminOut)
def admin_update_event(event_id: uuid.UUID, payload: EventIn, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "Esdeveniment no trobat")
    event.title = payload.title
    event.description = payload.description
    event.date = datetime.fromisoformat(payload.date)
    event.location = payload.location
    event.link = payload.link
    db.commit()
    db.refresh(event)
    return EventAdminOut(
        id=event.id, title=event.title, description=event.description,
        date=event.date.isoformat(), location=event.location, link=event.link,
        created_at=event.created_at.isoformat(),
    )


@router.delete("/events/{event_id}", status_code=204)
def admin_delete_event(event_id: uuid.UUID, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "Esdeveniment no trobat")
    db.delete(event)
    db.commit()
