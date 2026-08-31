from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.db.session import get_db
from app.core.security import decode_access_token
from app.services.auth import get_user_by_id
from app.models.user import Users, UserRole, SUPER_ROLES
from typing import cast

security = HTTPBearer()


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Users:
    token = credentials.credentials
    decoded = decode_access_token(token)
    if not decoded:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT token."
        )
    user_id, token_version = decoded
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid user, not found."
        )
    if cast(int, user.access_token_version) != token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT token."
        )
    return user


async def require_super(user: Users = Depends(get_current_user)) -> Users:
    if cast(UserRole, user.role) in SUPER_ROLES:
        return user
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Action forbidden, invalid user role.",
        )
