import pytest

from conftest import auth_header, create_product

CUSTOMER = {"name": "Abhi", "mobile": "+919876543210", "email": "abhi@example.com"}
TAX = {"tax": 10}


def cash_body():
    return {"customer": CUSTOMER, "method": "cash", "gateway": None}


def stripe_body():
    return {"customer": CUSTOMER, "method": "online", "gateway": "stripe"}


def razorpay_body():
    return {"customer": CUSTOMER, "method": "online", "gateway": "razorpay"}


@pytest.mark.asyncio
async def test_get_order_items_not_found(user_client):
    resp = await user_client.get("/orders/9999/items")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_superadmin_lists_all_orders(super_client, super_token, user_client):
    prod = await create_product(super_client, super_token, inventory=5)
    await user_client.post(f"/orders/{prod['id']}", params=TAX, json=cash_body())

    listed = await super_client.get("/orders")
    assert listed.status_code == 200
    assert len(listed.json()) >= 1


@pytest.mark.asyncio
async def test_checkout_fails_when_cart_product_deleted(
    super_client, super_token, user_client
):
    prod = await create_product(super_client, super_token, inventory=5)
    await user_client.post(f"/cart/{prod['id']}/add_product")
    await super_client.delete(
        f"/products/{prod['id']}", headers=auth_header(super_token)
    )

    resp = await user_client.post(
        "/orders/checkout/cart", params=TAX, json=cash_body()
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_direct_buy_payment_gateway_failure(
    monkeypatch, super_client, super_token, user_client
):
    class FailingAdapter:
        def create_payment(self, order, payment):
            raise RuntimeError("gateway down")

    monkeypatch.setattr(
        "app.services.orders.PaymentGatewayFactory.get",
        lambda gateway: FailingAdapter(),
    )

    prod = await create_product(super_client, super_token, inventory=5)
    resp = await user_client.post(
        f"/orders/{prod['id']}", params=TAX, json=stripe_body()
    )
    assert resp.status_code == 503
    inv = (await user_client.get(f"/products/{prod['id']}")).json()["inventory"]
    assert inv == 5


@pytest.mark.asyncio
async def test_checkout_cart_payment_gateway_failure(
    monkeypatch, super_client, super_token, user_client
):
    class FailingAdapter:
        def create_payment(self, order, payment):
            raise RuntimeError("gateway down")

    monkeypatch.setattr(
        "app.services.orders.PaymentGatewayFactory.get",
        lambda gateway: FailingAdapter(),
    )

    prod = await create_product(super_client, super_token, inventory=5)
    await user_client.post(f"/cart/{prod['id']}/add_product")
    resp = await user_client.post(
        "/orders/checkout/cart", params=TAX, json=stripe_body()
    )
    assert resp.status_code == 503
    cart = await user_client.get("/cart")
    assert cart.json() == []
    inv = (await user_client.get(f"/products/{prod['id']}")).json()["inventory"]
    assert inv == 5


@pytest.mark.asyncio
async def test_invalid_but_parseable_mobile_rejected(
    user_client, super_client, super_token
):
    prod = await create_product(super_client, super_token)
    resp = await user_client.post(
        f"/orders/{prod['id']}",
        params=TAX,
        json={
            "customer": {"name": "Abhi", "mobile": "+911234"},
            "method": "cash",
            "gateway": None,
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_direct_buy_cash(super_client, super_token, user_client):
    prod = await create_product(super_client, super_token, inventory=5)
    resp = await user_client.post(
        f"/orders/{prod['id']}", params=TAX, json=cash_body()
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["order_status"] == "successful"
    assert body["payment"]["status"] == "successful"
    assert body["payment"]["gateway"] == "cash"
    assert body["gateway_client"] is None
    assert body["total_items"] == 1
    inv = (await user_client.get(f"/products/{prod['id']}")).json()["inventory"]
    assert inv == 4


@pytest.mark.asyncio
async def test_direct_buy_online_stripe(super_client, super_token, user_client):
    prod = await create_product(super_client, super_token, inventory=5)
    resp = await user_client.post(
        f"/orders/{prod['id']}", params=TAX, json=stripe_body()
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["order_status"] == "pending"
    assert body["payment"]["status"] == "pending"
    assert body["payment"]["gateway"] == "stripe"
    assert body["payment"]["transaction_reference"] == "test_pi_123"
    assert body["gateway_client"] == {"client_secret": "test_secret_abc"}
    inv = (await user_client.get(f"/products/{prod['id']}")).json()["inventory"]
    assert inv == 4


@pytest.mark.asyncio
async def test_direct_buy_online_razorpay(super_client, super_token, user_client):
    prod = await create_product(super_client, super_token, inventory=5)
    resp = await user_client.post(
        f"/orders/{prod['id']}", params=TAX, json=razorpay_body()
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["payment"]["gateway"] == "razorpay"
    assert body["payment"]["transaction_reference"] == "test_rp_123"
    assert body["gateway_client"] == {"checkout_url": "https://checkout.razorpay.com/test"}


@pytest.mark.asyncio
async def test_direct_buy_invalid_product(user_client):
    resp = await user_client.post(
        "/orders/9999", params=TAX, json=cash_body()
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_direct_buy_out_of_stock(super_client, super_token, user_client):
    prod = await create_product(super_client, super_token, inventory=1)
    # Another user drains the last unit first.
    other = await user_client.post(
        f"/orders/{prod['id']}", params=TAX, json=cash_body()
    )
    assert other.status_code == 200
    resp = await user_client.post(
        f"/orders/{prod['id']}", params=TAX, json=cash_body()
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cash_with_gateway_rejected(user_client, super_client, super_token):
    prod = await create_product(super_client, super_token)
    resp = await user_client.post(
        f"/orders/{prod['id']}",
        params=TAX,
        json={"customer": CUSTOMER, "method": "cash", "gateway": "stripe"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_online_without_gateway_rejected(user_client, super_client, super_token):
    prod = await create_product(super_client, super_token)
    resp = await user_client.post(
        f"/orders/{prod['id']}",
        params=TAX,
        json={"customer": CUSTOMER, "method": "online", "gateway": None},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_online_with_unsupported_gateway_rejected(
    user_client, super_client, super_token
):
    prod = await create_product(super_client, super_token)
    resp = await user_client.post(
        f"/orders/{prod['id']}",
        params=TAX,
        json={"customer": CUSTOMER, "method": "online", "gateway": "billdesk"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_mobile_rejected(user_client, super_client, super_token):
    prod = await create_product(super_client, super_token)
    resp = await user_client.post(
        f"/orders/{prod['id']}",
        params=TAX,
        json={
            "customer": {"name": "Abhi", "mobile": "not-a-number"},
            "method": "cash",
            "gateway": None,
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_checkout_cart_cash(super_client, super_token, user_client):
    a = await create_product(super_client, super_token, name="A", inventory=5)
    b = await create_product(super_client, super_token, name="B", inventory=5)
    await user_client.post(f"/cart/{a['id']}/add_product")
    await user_client.post(f"/cart/{b['id']}/add_product")
    await user_client.post(f"/cart/{b['id']}/add_product")  # qty 2 of B

    resp = await user_client.post(
        "/orders/checkout/cart", params=TAX, json=cash_body()
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["order_status"] == "successful"
    assert body["total_items"] == 3
    assert body["payment"]["status"] == "successful"

    # Cart must be emptied by checkout.
    cart = await user_client.get("/cart")
    assert cart.json() == []
    # Inventory decremented by the bought quantities.
    inv_a = (await user_client.get(f"/products/{a['id']}")).json()["inventory"]
    inv_b = (await user_client.get(f"/products/{b['id']}")).json()["inventory"]
    assert inv_a == 4 and inv_b == 3


@pytest.mark.asyncio
async def test_checkout_cart_online(super_client, super_token, user_client):
    a = await create_product(super_client, super_token, name="A", inventory=5)
    await user_client.post(f"/cart/{a['id']}/add_product")
    resp = await user_client.post(
        "/orders/checkout/cart", params=TAX, json=stripe_body()
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["order_status"] == "pending"
    assert body["payment"]["status"] == "pending"
    assert body["gateway_client"] == {"client_secret": "test_secret_abc"}
    cart = await user_client.get("/cart")
    assert cart.json() == []


@pytest.mark.asyncio
async def test_checkout_empty_cart(user_client):
    resp = await user_client.post(
        "/orders/checkout/cart", params=TAX, json=cash_body()
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_orders_and_items(super_client, super_token, user_client):
    prod = await create_product(super_client, super_token, name="Widget", inventory=5)
    order = await user_client.post(
        f"/orders/{prod['id']}", params=TAX, json=cash_body()
    )
    order_id = order.json()["id"]

    listed = await user_client.get("/orders")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    one = await user_client.get(f"/orders/{order_id}")
    assert one.status_code == 200
    assert one.json()["id"] == order_id

    items = await user_client.get(f"/orders/{order_id}/items")
    assert items.status_code == 200
    assert len(items.json()) == 1
    assert items.json()[0]["product_name"] == "Widget"


@pytest.mark.asyncio
async def test_get_order_not_found(user_client):
    resp = await user_client.get("/orders/9999")
    assert resp.status_code == 404
