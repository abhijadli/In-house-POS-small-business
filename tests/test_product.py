import pytest

from conftest import auth_header, create_product


@pytest.mark.asyncio
async def test_create_product_requires_super(client, user_token):
    resp = await client.post(
        "/products",
        json={"name": "X", "price": 10.0, "discount": 0.0, "inventory": 1},
        headers=auth_header(user_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_product(super_client, super_token):
    prod = await create_product(super_client, super_token, name="Widget")
    assert prod["name"] == "Widget"
    assert prod["inventory"] == 5
    assert prod["id"]


@pytest.mark.asyncio
async def test_create_product_invalid_price(super_client, super_token):
    resp = await super_client.post(
        "/products",
        json={"name": "X", "price": -1.0, "discount": 0.0, "inventory": 1},
        headers=auth_header(super_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_products(super_client, super_token, user_client):
    await create_product(super_client, super_token, name="A")
    await create_product(super_client, super_token, name="B")
    resp = await user_client.get("/products")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert names == ["A", "B"]  # ordered by name asc


@pytest.mark.asyncio
async def test_get_product_by_id(super_client, super_token, user_client):
    prod = await create_product(super_client, super_token, name="Widget")
    resp = await user_client.get(f"/products/{prod['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Widget"


@pytest.mark.asyncio
async def test_get_product_not_found(user_client):
    resp = await user_client.get("/products/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_inventory(super_client, super_token):
    prod = await create_product(super_client, super_token, inventory=5)
    resp = await super_client.patch(
        f"/products/{prod['id']}/inventory",
        params={"new_inventory": 20},
        headers=auth_header(super_token),
    )
    assert resp.status_code == 200
    assert resp.json()["inventory"] == 20


@pytest.mark.asyncio
async def test_update_product_details(super_client, super_token):
    prod = await create_product(super_client, super_token, name="Widget", price=100.0)
    resp = await super_client.patch(
        f"/products/{prod['id']}/details",
        json={"name": "Gadget", "price": 120.0},
        headers=auth_header(super_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Gadget"
    assert float(body["price"]) == 120.0


@pytest.mark.asyncio
async def test_delete_product(super_client, super_token, user_client):
    prod = await create_product(super_client, super_token, name="Widget")
    resp = await super_client.delete(
        f"/products/{prod['id']}", headers=auth_header(super_token)
    )
    assert resp.status_code == 200
    # Soft-deleted products are hidden from listings/lookups.
    after = await user_client.get(f"/products/{prod['id']}")
    assert after.status_code == 404


@pytest.mark.asyncio
async def test_delete_product_not_found(super_client, super_token):
    resp = await super_client.delete(
        "/products/9999", headers=auth_header(super_token)
    )
    assert resp.status_code == 404
