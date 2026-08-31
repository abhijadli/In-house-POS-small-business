from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.schema.user import UserCreate
from app.models.user import Users, UserRole, SUPER_ROLES
from app.core.security import hash_password, verify_password, create_access_token
from app.core.refresh_token import create_refresh_token, revoke_refresh_token
from app.exception.auth_exception import (
    UsernameNotAvailableError,
    InvalidUserError,
    InvalidRequestError,
    InvalidLoginDetailsError
)
from typing import cast


# Function to get user by username
async def get_user_by_username(db: AsyncSession, username: str) -> Users | None:
    result = await db.execute(
        select(Users).where(Users.username == username, Users.is_deleted == False)
    )
    return result.scalar_one_or_none()


# Function to get user by id
async def get_user_by_id(db: AsyncSession, id: int) -> Users | None:
    result = await db.execute(
        select(Users).where(Users.id == id, Users.is_deleted == False)
    )
    return result.scalar_one_or_none()


# Function to authenticate a user
async def authenticate_user(db: AsyncSession, user_details: UserCreate) -> Users | None:
    user: Users | None = await get_user_by_username(db, user_details.username)
    if not user:
        return None
    return (
        user
        if verify_password(user_details.password, cast(str, user.hashed_password))
        else None
    )


# Function to create a new user
async def create_new_user(db: AsyncSession, details: UserCreate) -> Users:
    result = await get_user_by_username(db, details.username)
    if result:
        raise UsernameNotAvailableError()
    # Pending
    user = Users(
        username=details.username, hashed_password=hash_password(details.password)
    )
    # Transient
    db.add(user)
    # Persistent
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise UsernameNotAvailableError()
    await db.refresh(user)
    return user


# Function to login a user
async def login_user(db: AsyncSession, login_details: UserCreate) -> tuple[str, str]:
    user: Users | None = await authenticate_user(db, login_details)
    if not user:
        raise InvalidLoginDetailsError()
    return create_access_token(
        cast(int, user.id), cast(int, user.access_token_version)
    ), await create_refresh_token(db, cast(int, user.id))


# Admin can only change user's passwords
# Superadmin can change any password
async def update_password(
    db: AsyncSession, username: str, new_password: str, current_user: Users
):
    user: Users | None = await get_user_by_username(db, username)
    if not user:
        raise InvalidUserError()
    if (
        cast(UserRole, current_user.role) == UserRole.ADMIN
        and cast(UserRole, user.role) in SUPER_ROLES
    ):
        raise InvalidRequestError()
    setattr(user, "hashed_password", hash_password(new_password))
    setattr(
        user,
        "access_token_version",
        cast(int, user.access_token_version) + 1,
    )
    await db.commit()
    await db.refresh(user)
    await revoke_refresh_token(db, cast(int, user.id))
    return user


async def make_user_admin(db: AsyncSession, user_id: int, current_user: Users):
    if cast(str, current_user.role) not in SUPER_ROLES:
        raise InvalidRequestError()
    user: Users | None = await get_user_by_id(db, user_id)
    if not user:
        raise InvalidUserError()
    setattr(user, "role", UserRole.ADMIN)
    await db.commit()
    await db.refresh(user)
    return user


# Function to delete a user
async def delete_user(db: AsyncSession, id: int, current_user: Users):
    user: Users | None = await get_user_by_id(db, id)
    if not user:
        raise InvalidUserError()
    # Superadmin can never be deleted
    if cast(UserRole, user.role) == UserRole.SUPERADMIN:
        raise InvalidRequestError()
    # An admin can't delete itself
    elif cast(int, user.id) == cast(int, current_user.id):
        raise InvalidRequestError()
    # Only Superadmin can delete an admin
    elif (
        cast(UserRole, user.role) == UserRole.ADMIN
        and cast(UserRole, current_user.role) != UserRole.SUPERADMIN
    ):
        raise InvalidRequestError()

    # Set is_deleted to True
    setattr(user, "is_deleted", True)
    await db.commit()
    await db.refresh(user)
    return user
