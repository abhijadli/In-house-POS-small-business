from fastapi import Depends, APIRouter, HTTPException, status
from app.db.session import get_db
from app.core.deps import require_super, get_current_user
from app.services.product import (
    get_product_by_id,
    get_all_products,
    add_product_to_catalogue,
    remove_product_from_catalogue,
    patch_inventory,
    patch_product,
)
from app.schema.product import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.models.user import Users
from app.models.product import Products
from app.exception.product_exception import (
    InvalidProductError,
)

from sqlalchemy.ext.asyncio import AsyncSession


from typing import Any, cast

product_router = APIRouter()


# Create
@product_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ProductResponse,
    summary="New product creation",
)
async def create_new_product_for_catalogue(
    product: ProductCreate,
    user: Users = Depends(require_super),
    db: AsyncSession = Depends(get_db),
):
    return await add_product_to_catalogue(db, product)


# Read
@product_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=list[ProductResponse],
    summary="To list all available undeleted products",
)
async def list_all_products_in_catalogue(
    db: AsyncSession = Depends(get_db), user: Users = Depends(get_current_user)
):
    return await get_all_products(db)


@product_router.get(
    "/{id}",
    status_code=status.HTTP_200_OK,
    response_model=ProductResponse,
    summary="To search available product by id",
)
async def search_product_by_id_in_catalogue(
    id: int, db: AsyncSession = Depends(get_db), user: Users = Depends(get_current_user)
):
    product: Products | None = await get_product_by_id(db, id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid product, not found."
        )
    return product


# Update
@product_router.patch(
    "/{id}/inventory",
    status_code=status.HTTP_200_OK,
    summary="Update inventory of a product",
)
async def update_inventory_in_catalogue(
    id: int,
    new_inventory: int,
    db: AsyncSession = Depends(get_db),
    user: Users = Depends(require_super),
):
    try:
        return await patch_inventory(db, id, new_inventory)
    except InvalidProductError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid product, not found."
        )


@product_router.patch(
    "/{id}/details",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="To change product details",
)
async def update_product_details_in_catalogue(
    id: int,
    details: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    user: Users = Depends(require_super),
):
    update: dict[str, Any] = details.model_dump(exclude_unset=True)
    try:
        return await patch_product(db, id, update)
    except InvalidProductError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid product, not found."
        )


# Delete
@product_router.delete(
    "/{id}",
    status_code=status.HTTP_200_OK,
    response_model=ProductResponse,
    summary="Delete a product through its id",
)
async def delete_product_from_catalogue(
    id: int, db: AsyncSession = Depends(get_db), user: Users = Depends(require_super)
):
    try:
        return await remove_product_from_catalogue(db, id)
    except InvalidProductError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid product, not found."
        )
