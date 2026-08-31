from fastapi import APIRouter, HTTPException, status, Depends
from typing import cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.models.user import Users
from app.schema.cart import ProductCartResponse
from app.exception.cart_exception import NoEntryFoundInCart
from app.exception.product_exception import InvalidProductError
from app.exception.order_exception import ProductOutOfStock
from app.core.deps import get_current_user, get_db
from app.services.cart import (
    add_product_entry_to_cart,
    decrease_product_quantity_from_cart,
    delete_product_entry_from_cart,
    get_all_cart_items_for_user,
    empty_cart_for_user,
)

cart_router = APIRouter()


# create
@cart_router.post(
    "/{product_id}/add_product",
    status_code=status.HTTP_200_OK,
    response_model=ProductCartResponse,
    summary="Add product to cart",
)
async def add_product_to_cart(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    user: Users = Depends(get_current_user),
):
    try:
        return await add_product_entry_to_cart(db, product_id, cast(int, user.id))
    except InvalidProductError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid product, not found."
        )
    except ProductOutOfStock:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product out of stock, conflict.",
        )
    # In case of db failures
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not add product to cart.",
        )


# read
@cart_router.get(
    "",
    response_model=list[ProductCartResponse],
    status_code=status.HTTP_200_OK,
    summary="Get complete cart of a user",
)
async def list_cart(
    db: AsyncSession = Depends(get_db),
    user: Users = Depends(get_current_user),
):
    return await get_all_cart_items_for_user(db, cast(int, user.id))


# update


# delete
@cart_router.delete(
    "/{product_id}/delete_product",
    response_model=ProductCartResponse | str,
    status_code=status.HTTP_200_OK,
    summary="Decrease product quantity by one from cart",
)
async def decrease_quantity_from_cart(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    user: Users = Depends(get_current_user),
):
    try:
        return await decrease_product_quantity_from_cart(
            db, product_id, cast(int, user.id)
        )
    # In case of db failures
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not remove product from cart.",
        )
    except InvalidProductError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid product, not found."
        )
    except NoEntryFoundInCart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No entry in cart for the product",
        )


@cart_router.delete(
    "/{product_id}/delete_entry",
    response_model=str,
    status_code=status.HTTP_200_OK,
    summary="Decrease product quantity by one from cart",
)
async def remove_entry_from_cart(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    user: Users = Depends(get_current_user),
):
    try:
        return await delete_product_entry_from_cart(db, product_id, cast(int, user.id))
    # In case of db failures
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not remove product from cart.",
        )
    except InvalidProductError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid product, not found."
        )
    except NoEntryFoundInCart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No entry in cart for the product",
        )


@cart_router.delete(
    "/empty_cart",
    response_model=str,
    status_code=status.HTTP_200_OK,
    summary="Empty the cart for a user",
)
async def empty_cart(
    db: AsyncSession = Depends(get_db),
    user: Users = Depends(get_current_user),
):
    try:
        await empty_cart_for_user(db, cast(int, user.id))
        return "Cart empty."
    # In case of db failures
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not empty cart.",
        )
    except InvalidProductError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid product, not found."
        )
    except NoEntryFoundInCart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No entry in cart for the product",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not empty cart.",
        )
        
