from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from app.schema.product import ProductCreate
from app.models.product import Products
from app.exception.product_exception import (
    InvalidProductError,
)
from typing import Any, cast


async def get_product_by_id(db: AsyncSession, id: int) -> Products | None:
    result = await db.execute(
        select(Products).where(Products.id == id, Products.is_deleted.is_(False))
    )
    result = result.scalar_one_or_none()
    if result:
        return result


# List all available products
async def get_all_products(db: AsyncSession) -> list[Products]:
    result = await db.execute(
        select(Products)
        .where(Products.is_deleted.is_(False))
        .order_by(Products.name.asc())
    )
    result = result.scalars().all()
    return list(result)


# Add product to catalogue
async def add_product_to_catalogue(
    db: AsyncSession, product_details: ProductCreate
) -> Products:
    product: Products = Products(
        name=product_details.name,
        description=product_details.description,
        price=product_details.price,
        discount=product_details.discount,
        inventory=product_details.inventory,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


# Update a product inventory by its id
async def patch_inventory(db: AsyncSession, id: int, inventory: int) -> Products:
    product: Products | None = await get_product_by_id(db, id)
    if not product:
        raise InvalidProductError()
    setattr(product, "inventory", inventory)
    await db.commit()
    await db.refresh(product)
    return product


# Update a product inventory by its id
async def patch_product(db: AsyncSession, id: int, details: dict[str, Any]) -> Products:
    product: Products | None = await get_product_by_id(db, id)
    if not product:
        raise InvalidProductError()
    for field, values in details.items():
        setattr(product, field, values)
    await db.commit()
    await db.refresh(product)
    return product


# Remove product from catalogue
async def remove_product_from_catalogue(db: AsyncSession, id: int) -> Products:
    product = await get_product_by_id(db, id)
    if not product:
        raise InvalidProductError()
    setattr(product, "is_deleted", True)
    await db.commit()
    await db.refresh(product)
    return product

# Restock product after order failure
async def restock_product(db: AsyncSession, product_id: int, quantity: int) -> None:
    await db.execute(
        update(Products).where(Products.id == product_id)
        .values(inventory=Products.inventory + quantity)
    )
