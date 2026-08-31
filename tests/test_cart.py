import pytest

from conftest import auth_header, create_product


@pytest.mark.asyncio
async def test_add_to_cart_and_inventory_decrements(
    super_client, super_token, user_client
):
    prod = await create_product(super_client, super_token, inventory=5)
    resp = await user_client.post(f"/cart/{prod['id']}/add_product")
    assert resp.status_code == 200
    assert resp.json()["quantity"] == 1

    inv = (await user_client.get(f"/products/{prod['id']}")).json()["inventory"]
    assert inv == 4


@pytest.mark.asyncio
async def test_add_same_product_increments_quantity(
    super_client, super_token, user_client
):
    prod = await create_product(super_client, super_token, inventory=5)
    await user_client.post(f"/cart/{prod['id']}/add_product")
    resp = await user_client.post(f"/cart/{prod['id']}/add_product")
    assert resp.json()["quantity"] == 2
    inv = (await user_client.get(f"/products/{prod['id']}")).json()["inventory"]
    assert inv == 3


@pytest.mark.asyncio
async def test_list_cart(super_client, super_token, user_client):
    prod = await create_product(super_client, super_token, name="A")
    await user_client.post(f"/cart/{prod['id']}/add_product")
    resp = await user_client.get("/cart")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["product_id"] == prod["id"]


@pytest.mark.asyncio
async def test_decrease_quantity_restocks(
    super_client, super_token, user_client
):
    prod = await create_product(super_client, super_token, inventory=5)
    await user_client.post(f"/cart/{prod['id']}/add_product")
    await user_client.post(f"/cart/{prod['id']}/add_product")
    # qty is now 2, inventory 3
    resp = await user_client.delete(f"/cart/{prod['id']}/delete_product")
    assert resp.status_code == 200
    assert resp.json()["quantity"] == 1
    inv = (await user_client.get(f"/products/{prod['id']}")).json()["inventory"]
    assert inv == 4


@pytest.mark.asyncio
async def test_decrease_removes_entry_when_quantity_one(
    super_client, super_token, user_client
):
    prod = await create_product(super_client, super_token, inventory=5)
    await user_client.post(f"/cart/{prod['id']}/add_product")
    resp = await user_client.delete(f"/cart/{prod['id']}/delete_product")
    assert resp.status_code == 200
    # Entry gone, inventory fully restocked.
    cart = await user_client.get("/cart")
    assert cart.json() == []
    inv = (await user_client.get(f"/products/{prod['id']}")).json()["inventory"]
    assert inv == 5


@pytest.mark.asyncio
async def test_decrease_no_entry(super_client, super_token, user_client):
    prod = await create_product(super_client, super_token)
    resp = await user_client.delete(f"/cart/{prod['id']}/delete_product")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_entry_restocks(super_client, super_token, user_client):
    prod = await create_product(super_client, super_token, inventory=5)
    await user_client.post(f"/cart/{prod['id']}/add_product")
    await user_client.post(f"/cart/{prod['id']}/add_product")  # qty 2
    resp = await user_client.delete(f"/cart/{prod['id']}/delete_entry")
    assert resp.status_code == 200
    cart = await user_client.get("/cart")
    assert cart.json() == []
    inv = (await user_client.get(f"/products/{prod['id']}")).json()["inventory"]
    assert inv == 5


@pytest.mark.asyncio
async def test_empty_cart_restocks(super_client, super_token, user_client):
    a = await create_product(super_client, super_token, name="A", inventory=5)
    b = await create_product(super_client, super_token, name="B", inventory=5)
    await user_client.post(f"/cart/{a['id']}/add_product")
    await user_client.post(f"/cart/{b['id']}/add_product")
    resp = await user_client.delete("/cart/empty_cart")
    assert resp.status_code == 200
    cart = await user_client.get("/cart")
    assert cart.json() == []
    inv_a = (await user_client.get(f"/products/{a['id']}")).json()["inventory"]
    inv_b = (await user_client.get(f"/products/{b['id']}")).json()["inventory"]
    assert inv_a == 5 and inv_b == 5


@pytest.mark.asyncio
async def test_empty_cart_when_empty(super_client, super_token, user_client):
    resp = await user_client.delete("/cart/empty_cart")
    # NoEntryFoundInCart -> 404
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_out_of_stock(super_client, super_token, user_client):
    prod = await create_product(super_client, super_token, inventory=1)
    await user_client.post(f"/cart/{prod['id']}/add_product")  # inventory -> 0
    resp = await user_client.post(f"/cart/{prod['id']}/add_product")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_add_invalid_product(user_client):
    resp = await user_client.post("/cart/9999/add_product")
    assert resp.status_code == 404
