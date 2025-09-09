from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.db.base import get_session
from app.core.db.schemas.auth import User
from app.core.jwt_utils import jwt_manager
from app.modules.auth import (
    fastapi_users,
    auth_backend,
    UserRead,
    UserCreate,
    UserUpdate,
    UserManager,
)


router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


async def authenticate_user(
    username: str, password: str, session: AsyncSession
) -> User | None:
    """Authenticate user with email and password"""
    result = await session.execute(select(User).where(User.email == username))
    user = result.scalar_one_or_none()

    if not user:
        return None

    # Verify password using fastapi-users password hashing
    user_manager = UserManager(None)
    if not user_manager.password_helper.verify_and_update(
        password, user.hashed_password
    )[0]:
        return None

    return user


@router.post("/login", tags=["auth"])
async def login(request: LoginRequest, session: AsyncSession = Depends(get_session)):
    """Login endpoint that returns RS256 JWT token"""
    user = await authenticate_user(request.username, request.password, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    # Create user data for token
    user_data = {
        "sub": f"user:{user.id}",
        "email": str(user.email),
        "user_id": user.id,
    }

    token = jwt_manager.generate_token(user_data)
    return {"idToken": token}


@router.get("/.well-known/jwks.json", tags=["auth"])
async def jwks():
    """JWKS endpoint for public key distribution"""
    return JSONResponse(content=jwt_manager.get_jwks())


@router.post("/introspect", tags=["auth"])
async def introspect(token: str):
    """Token introspection endpoint for debugging"""
    try:
        decoded = jwt_manager.verify_token(token)
        return decoded
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


# Include existing FastAPI Users routers
router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix=f"/{settings.app.version}/auth",
    tags=["auth-legacy"],
)

router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix=f"/{settings.app.version}/auth",
    tags=["auth"],
)

router.include_router(
    fastapi_users.get_reset_password_router(),
    prefix=f"/{settings.app.version}/auth",
    tags=["auth"],
)

router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix=f"/{settings.app.version}/users",
    tags=["users"],
)
