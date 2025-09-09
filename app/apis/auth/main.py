from fastapi import APIRouter

from app.core.config import settings
from app.modules.auth import (
    fastapi_users,
    auth_backend,
    UserRead,
    UserCreate,
    UserUpdate,
)


router = APIRouter()


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
