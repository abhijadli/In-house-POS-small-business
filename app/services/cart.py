from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from app.models.product import Products
from app.models.cart import ProductCart
from app.exception.product_exception import InvalidProductError
from app.exception.order_exception import ProductOutOfStock
from app.exception.cart_exception import NoEntryFoundInCart
from app.services.product import get_product_by_id, restock_product
from typing import cast


async def get_all_cart_items_for_user(
    db: AsyncSession, user_id: int
) -> list[ProductCart]:
    result = await db.execute(
        select(ProductCart)
        .where(ProductCart.user_id == user_id)
        .order_by(ProductCart.inserted_timestamp.desc())
    )
    return list(result.scalars().all())


async def get_product_entry_for_user_from_cart(
    db: AsyncSession, pid: int, uid: int
) -> tuple[ProductCart | None, Products]:
    product = await get_product_by_id(db, pid)
    if not product:
        raise InvalidProductError()
    entry = await db.execute(
        select(ProductCart).where(
            ProductCart.product_id == pid, ProductCart.user_id == uid
        )
    )
    return entry.scalar_one_or_none(), product


async def add_product_entry_to_cart(db: AsyncSession, pid: int, uid: int):
    entry, product = await get_product_entry_for_user_from_cart(db, pid, uid)
    try:
        # Checking and updating inventory
        inventory_update = await db.execute(
            update(Products)
            .where(
                Products.id == pid,
                Products.inventory > 0,
            )
            .values(inventory=Products.inventory - 1)
            .returning(Products.id)
        )
        updated_product_id = inventory_update.scalar_one_or_none()
        if updated_product_id is None:
            raise ProductOutOfStock()

        # Increasing quantity
        if entry:
            setattr(entry, "quantity", entry.quantity + 1)
        else:
            entry = ProductCart(product_id=pid, user_id=uid)
            db.add(entry)
        await db.commit()
        await db.refresh(product)
        await db.refresh(entry)
    except Exception:
        await db.rollback()
        raise
    return entry


async def decrease_product_quantity_from_cart(
    db: AsyncSession, pid: int, uid: int
) -> ProductCart | str:
    entry, product = await get_product_entry_for_user_from_cart(db, pid, uid)
    if not entry:
        raise NoEntryFoundInCart()
    try:
        # Restock one unit atomically
        await restock_product(db, pid, 1)
        # Decreasing quantity
        if cast(int, entry.quantity) > 1:
            setattr(entry, "quantity", entry.quantity - 1)
            await db.commit()
            await db.refresh(product)
            await db.refresh(entry)
            return entry
        # Deleting entry if quantity is only 1
        else:
            await db.delete(entry)
            await db.commit()
            await db.refresh(product)
            return "Product entry removed from cart."
    except Exception:
        await db.rollback()
        raise


async def delete_product_entry_from_cart(
    db: AsyncSession, pid: int, uid: int, whether_bought: bool = False
) -> str:
    entry, product = await get_product_entry_for_user_from_cart(db, pid, uid)
    if not entry:
        raise NoEntryFoundInCart()
    try:
        # Updating inventory if applicable
        if whether_bought == False:
            await restock_product(db, pid, cast(int, entry.quantity))
        await db.delete(entry)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return "Product entry removed from cart."


async def empty_cart_for_user(
    db: AsyncSession, user_id: int, whether_bought: bool = False
):
    try:
        all_products: list[ProductCart] = await get_all_cart_items_for_user(db, user_id)
        if not all_products:
            raise NoEntryFoundInCart()
        for entry in all_products:
            if whether_bought == False:
                product: Products | None = await get_product_by_id(
                    db, cast(int, entry.product_id)
                )
                if product:
                    await restock_product(
                        db, cast(int, entry.product_id), cast(int, entry.quantity)
                    )
            await db.delete(entry)
        await db.commit()
    except NoEntryFoundInCart:
        raise
    except Exception:
        await db.rollback()
        raise
