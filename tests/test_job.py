from datetime import datetime, timedelta

import pytest
from sqlalchemy import update

from conftest import AsyncSessionLocalTest, auth_header, create_product
import app.jobs.my_job as job_mod
from app.models.cart import ProductCart


@pytest.mark.asyncio
async def test_abandoned_cart_job_empties_and_restocks(
    super_client, super_token, user_client
):
    prod = await create_product(super_client, super_token, inventory=5)
    await user_client.post(f"/cart/{prod['id']}/add_product")
    # Inventory decremented to 4 by the add.
    assert (await user_client.get(f"/products/{prod['id']}")).json()["inventory"] == 4

    # Force the cart row to look abandoned (expires_at in the past).
    async with AsyncSessionLocalTest() as db:
        await db.execute(
            update(ProductCart)
            .where(ProductCart.product_id == prod["id"])
            .values(expires_at=datetime.utcnow() - timedelta(minutes=5))
        )
        await db.commit()

    # Point the job at the test database, then run it.
    job_mod.SessionLocal = AsyncSessionLocalTest
    await job_mod.my_job()

    # Cart should be emptied and inventory restocked.
    cart = await user_client.get("/cart")
    assert cart.json() == []
    inv = (await user_client.get(f"/products/{prod['id']}")).json()["inventory"]
    assert inv == 5


@pytest.mark.asyncio
async def test_job_skips_non_expired_cart(super_client, super_token, user_client):
    prod = await create_product(super_client, super_token, inventory=5)
    await user_client.post(f"/cart/{prod['id']}/add_product")
    # expires_at is 30 min in the future by default -> not abandoned.

    job_mod.SessionLocal = AsyncSessionLocalTest
    await job_mod.my_job()

    cart = await user_client.get("/cart")
    assert len(cart.json()) == 1
    inv = (await user_client.get(f"/products/{prod['id']}")).json()["inventory"]
    assert inv == 4  # unchanged
