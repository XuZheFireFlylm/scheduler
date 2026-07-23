"""Auth API router — /auth/*."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.schemas.auth import UserRegister, UserLogin, Token, UserRead
from app.services.auth_service import (
    create_user,
    get_user_by_username,
    get_user_by_email,
    authenticate_user,
    create_access_token,
    decode_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])
http_bearer = HTTPBearer(auto_error=False)


# ── Dependencies ──────────────────────────────────────────────────────────────
async def get_current_user_optional(
    creds: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID | None:
    """Return user_id if valid token present, else None."""
    if not creds:
        return None
    payload = decode_token(creds.credentials)
    if not payload:
        return None
    user_id_str = payload.get("sub")
    if not user_id_str:
        return None
    try:
        return uuid.UUID(user_id_str)
    except ValueError:
        return None


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    """Require a valid JWT. Raises 401 if missing or invalid."""
    payload = decode_token(creds.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="invalid_or_expired_token")
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="invalid_token_payload")
    try:
        return uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid_user_id_in_token")


# ── Routes ──────────────────────────────────────────────────────────────────
@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    # Check uniqueness
    if await get_user_by_username(db, body.username):
        raise HTTPException(status_code=409, detail="username_already_taken")
    if await get_user_by_email(db, body.email):
        raise HTTPException(status_code=409, detail="email_already_registered")

    user = await create_user(db, body.username, body.email, body.password)
    return user


@router.post("/login", response_model=Token)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate and return a JWT access token."""
    user = await authenticate_user(db, body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="invalid_username_or_password")

    from app.core.config import get_settings
    settings = get_settings()
    token = create_access_token(user.id, expires_delta=settings.JWT_EXPIRE_SECONDS)

    return Token(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRE_SECONDS,
    )


@router.get("/me", response_model=UserRead)
async def get_me(
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current authenticated user's profile."""
    from app.services.auth_service import get_user_by_id
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    return user
