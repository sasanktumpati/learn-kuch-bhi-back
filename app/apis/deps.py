from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from app.core.db.schemas.auth import User
from app.modules.auth.users import get_user_manager, get_jwt_strategy


async def current_user_or_query_token(
    access_token: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
    user_manager=Depends(get_user_manager),
) -> User:
    """Resolve current user from Authorization header or `access_token` query param.

    Useful for SSE, where setting custom headers is inconvenient. Falls back to
    query param token when header is missing.
    """
    token: Optional[str] = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif access_token:
        token = access_token

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    strategy = get_jwt_strategy()
    user = await strategy.read_token(token, user_manager)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return user

