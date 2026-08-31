from app.core.config import settings
from datetime import datetime, timedelta
from app.core.refresh_token_model import RefreshTokens
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import hashlib
import secrets


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# One active session per user
async def create_refresh_token(db: AsyncSession, user_id: int):
    await db.execute(
        update(RefreshTokens)
        .where(RefreshTokens.user_id == user_id)
        .values(is_revoked=True)
    )
    raw_token = generate_refresh_token()
    token_hash = hash_token(raw_token)
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    refresh_token = RefreshTokens(
        user_id=user_id, token_hash=token_hash, expires_at=expire
    )
    db.add(refresh_token)
    await db.commit()
    return raw_token


async def check_refresh_token_validity(db: AsyncSession, raw_token: str):
    token_hash = hash_token(raw_token)
    refresh_token = await db.execute(
        select(RefreshTokens).where(
            RefreshTokens.token_hash == token_hash,
            RefreshTokens.expires_at > datetime.utcnow(),
            RefreshTokens.is_revoked == False,
        )
    )
    return refresh_token.scalar_one_or_none()


async def revoke_refresh_token(db: AsyncSession, user_id: int):
    await db.execute(
        update(RefreshTokens)
        .where(RefreshTokens.user_id == user_id, RefreshTokens.is_revoked == False)
        .values(is_revoked=True)
    )
    await db.commit()
