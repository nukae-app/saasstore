import uuid

from pydantic import BaseModel, EmailStr


class MagicLinkRequest(BaseModel):
    email: EmailStr
    language: str = "ca"


class PasswordLoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None
    language: str = "ca"


class SetPasswordRequest(BaseModel):
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    name: str | None
    role: str
    language: str

    model_config = {"from_attributes": True}


# --- Carrito y checkout ---
