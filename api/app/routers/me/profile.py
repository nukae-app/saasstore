import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import User
from ...services.security import get_current_user

router = APIRouter(prefix="/me", tags=["me"])


class ProfilePatch(BaseModel):
    name: str | None = None
    phone: str | None = None
    language: str | None = None
    consent_newsletter: bool | None = None


class MeFullOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None
    phone: str | None
    role: str
    language: str
    consent_newsletter: bool
    active: bool

    model_config = {"from_attributes": True}


@router.get("/profile", response_model=MeFullOut)
def get_profile(user: User = Depends(get_current_user)):
    return user


@router.patch("/profile", response_model=MeFullOut)
def update_profile(
    payload: ProfilePatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, val)
    db.commit()
    db.refresh(user)
    return user
