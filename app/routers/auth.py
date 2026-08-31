from fastapi import APIRouter, status, HTTPException, Depends
from app.db.session import get_db
from app.core.deps import get_current_user, require_super
from app.core.security import create_access_token
from app.schema.user import UserCreate, UserResponse, PasswordUpdate
from app.models.user import Users
from app.core.Token_schema import RefreshTokenRequest, Token
from app.core.refresh_token import (
    create_refresh_token,
    check_refresh_token_validity,
    revoke_refresh_token,
)
from app.services.auth import (
    create_new_user,
    login_user,
    delete_user,
    update_password,
    get_user_by_id,
    make_user_admin,
)
from sqlalchemy.ext.asyncio import AsyncSession
from app.exception.auth_exception import (
    InvalidUserError,
    UsernameNotAvailableError,
    InvalidRequestError,
    InvalidLoginDetailsError,
)
from typing import cast

auth_router = APIRouter()


# Create
@auth_router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="New user creation",
)
async def user_registration(
    details: UserCreate,
    db: AsyncSession = Depends(get_db),
    user: Users = Depends(require_super),
):
    try:
        return await create_new_user(db, details)
    except UsernameNotAvailableError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The username is not available to register as it is already in use.",
        )


@auth_router.post(
    "/login", response_model=Token, status_code=status.HTTP_200_OK, summary="User Login"
)
async def user_login(details: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        access_token, refresh_token = await login_user(db, details)
        return Token(
            access_token=access_token, refresh_token=refresh_token, token_type="bearer"
        )
    except InvalidLoginDetailsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials."
        )


@auth_router.post(
    "/refresh",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
)
async def refresh_user(data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    refresh_token = await check_refresh_token_validity(db, data.refresh_token)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Refresh Token."
        )
    user: Users | None = await get_user_by_id(db, cast(int, refresh_token.user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid user, not found."
        )
    return Token(
        access_token=create_access_token(
            cast(int, user.id), cast(int, user.access_token_version)
        ),
        refresh_token=await create_refresh_token(db, cast(int, user.id)),
    )


@auth_router.post(
    "/logout",
    response_model=str,
    status_code=status.HTTP_200_OK,
    summary="To log out a user",
)
async def logout_user(data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    refresh_token = await check_refresh_token_validity(db, data.refresh_token)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Refresh Token."
        )
    await revoke_refresh_token(db, cast(int, refresh_token.user_id))
    return "Successfully logged out."


# Read
"""@auth_router.get(
    "/{id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user by id",
)
async def search_user_by_id(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super),
): 
    await get_user_by_id(db, id)
    ..."""


# Update
@auth_router.patch(
    "/password",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=UserResponse,
    summary="User password update",
)
async def user_password_update(
    details: PasswordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Users = Depends(require_super),
):
    try:
        return await update_password(
            db, details.username, details.new_password, current_user
        )
    except InvalidUserError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid user, not found."
        )
    except InvalidRequestError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Request, action not allowed.",
        )


@auth_router.patch(
    "/{id}",
    status_code=status.HTTP_200_OK,
    response_model=UserResponse,
    summary="Promoting user to admin.",
)
async def make_admin(
    id: int, db: AsyncSession = Depends(get_db), user: Users = Depends(get_current_user)
):
    try:
        return await make_user_admin(db, id, user)
    except InvalidUserError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid user, user not found.",
        )
    except InvalidRequestError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid request, action forbidden.",
        )


# Delete
@auth_router.delete(
    "/{id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="User deletion through id",
)
async def user_deletion(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Users = Depends(require_super),
):
    try:
        return await delete_user(db, id, current_user)
    except InvalidUserError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid user, not found."
        )
    except InvalidRequestError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Request, action not allowed.",
        )
