from fastapi import APIRouter, status, Depends, HTTPException
from app.core.deps import get_current_user, get_db
from app.schema.orders import (
    OrderDetailResponse,
    OrderCreateResponse,
    OrderRequest,
    OrderItemResponse,
)
from app.services.orders import (
    search_order_by_id,
    list_all_orders,
    buy_product_through_id,
    search_order_items_by_order_id,
    checkout_cart_for_user,
)
from app.models.user import Users
from sqlalchemy.ext.asyncio import AsyncSession
from app.exception.order_exception import InvalidOrderError, ProductOutOfStock
from app.exception.product_exception import InvalidProductError
from app.exception.payment_exception import PaymentGatewayError
from app.exception.cart_exception import CartEmptyError
from decimal import Decimal

order_router = APIRouter()


# Create
@order_router.post(
    "/checkout/cart",
    response_model=OrderCreateResponse,
    summary="Checkout the cart for the current user",
)
async def checkout_cart(
    tax: Decimal,
    payload: OrderRequest,
    db: AsyncSession = Depends(get_db),
    user: Users = Depends(get_current_user),
):
    try:
        order, gateway_client = await checkout_cart_for_user(db, user, tax, payload)
    except CartEmptyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty."
        )
    except InvalidProductError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A product in the cart is no longer available. Remove it and retry.",
        )
    except PaymentGatewayError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment gateway could not be reached. Order marked as failed.",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sorry for the inconvenience, could not process checkout.",
        )

    response = OrderCreateResponse.model_validate(order)
    response.gateway_client = gateway_client
    return response


@order_router.post(
    "/{product_id}",
    summary="Order product by id",
    response_model=OrderCreateResponse,
    description="Order product directly without adding it to cart.",
)
async def order_product_by_id(
    product_id: int,
    tax: Decimal,
    payload: OrderRequest,
    db: AsyncSession = Depends(get_db),
    user: Users = Depends(get_current_user),
):
    try:
        order, gateway_client = await buy_product_through_id(
            db, product_id, tax, user, payload
        )
    except InvalidProductError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found, invalid product.",
        )
    except ProductOutOfStock:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden action, produt out of stock.",
        )
    except PaymentGatewayError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment gateway could not be reached. Order marked as failed.",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sorry for the inconvenience, could not process order.",
        )

    response = OrderCreateResponse.model_validate(order)
    response.gateway_client = gateway_client
    return response


# Read
@order_router.get(
    "",
    response_model=list[OrderDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="To get all orders as per user role",
)
async def get_all_orders(
    db: AsyncSession = Depends(get_db), user: Users = Depends(get_current_user)
):
    return await list_all_orders(db, user)


@order_router.get(
    "/{id}",
    response_model=OrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="To get an order by id",
)
async def get_order_by_id(
    id: int, db: AsyncSession = Depends(get_db), user: Users = Depends(get_current_user)
):
    try:
        return await search_order_by_id(db, id, user)
    except InvalidOrderError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inavlid order id, order not found.",
        )


@order_router.get(
    "/{id}/items",
    response_model=list[OrderItemResponse],
    status_code=status.HTTP_200_OK,
    summary="To get items of an order by id",
)
async def get_order_items_by_id(
    id: int, db: AsyncSession = Depends(get_db), user: Users = Depends(get_current_user)
):
    try:
        return await search_order_items_by_order_id(db, id, user)
    except InvalidOrderError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inavlid order id, order not found.",
        )


# Update
