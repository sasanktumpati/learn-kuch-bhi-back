from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.modules.auth import (
    fastapi_users,
    auth_backend,
    UserRead,
    UserCreate,
    UserUpdate,
)


router = APIRouter()


@router.get("/.well-known/jwks.json", tags=["auth"])
async def jwks():
    """JWKS endpoint for public key distribution"""
    from app.modules.auth.users import get_jwt_strategy

    strategy = get_jwt_strategy()
    return JSONResponse(content=strategy.get_jwks())


# Include FastAPI Users routers
router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix=f"/{settings.app.version}/auth",
    tags=["auth"],
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
