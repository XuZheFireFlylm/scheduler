"""Auth Pydantic schemas."""
import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# ── Register ──────────────────────────────────────────────────────────────────
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


# ── Login ─────────────────────────────────────────────────────────────────────
class UserLogin(BaseModel):
    username: str
    password: str


# ── Token ─────────────────────────────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int   # seconds


# ── UserRead (response) ───────────────────────────────────────────────────────
class UserRead(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    total_contribution: int
    created_at: datetime

    model_config = {"from_attributes": True}
