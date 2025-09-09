from typing import AsyncIterator, Optional, cast

from fastapi import Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.authentication.transport import Transport
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from fastapi_users.manager import BaseUserManager, IntegerIDMixin
from fastapi_users import schemas as fa_schemas

from pydantic import EmailStr

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db.base import get_session
from app.core.db.schemas.auth import User


# Pydantic schemas (restrict API to not set privileged flags)
class UserRead(fa_schemas.BaseUser[int]):
    id: int
    email: EmailStr


class UserCreate(fa_schemas.BaseUserCreate):
    email: EmailStr
    password: str


class UserUpdate(fa_schemas.BaseUserUpdate):
    email: Optional[EmailStr] = None
    password: Optional[str] = None


async def get_user_db(
    session: AsyncSession = Depends(get_session),
) -> AsyncIterator[SQLAlchemyUserDatabase]:
    yield SQLAlchemyUserDatabase(session, User)


class UserManager(IntegerIDMixin, BaseUserManager[User, int]):  # type: ignore[type-arg]
    reset_password_token_secret = settings.app.jwt_secret
    verification_token_secret = settings.app.jwt_secret

    # Optional hooks you can customize later
    # async def on_after_register(self, user: User, request=None):
    #     pass


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
) -> AsyncIterator[UserManager]:
    yield UserManager(user_db)


# Auth backend: JWT over Bearer, using versioned path for login
bearer_transport = BearerTransport(tokenUrl=f"{settings.app.version}/auth/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.app.jwt_secret, lifetime_seconds=60 * 60 * 24)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cast(Transport, bearer_transport),
    get_strategy=get_jwt_strategy,
)


fastapi_users = FastAPIUsers[User, int](  # type: ignore[type-arg]
    get_user_manager,
    [auth_backend],
)
