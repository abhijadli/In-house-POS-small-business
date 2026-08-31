import pytest

from conftest import auth_header, create_product

CUSTOMER = {"name": "Abhi", "mobile": "+919876543210", "email": "abhi@example.com"}
TAX = {"tax": 10}


def stripe_body():
    return {"customer": CUSTOMER, "method": "online", "gateway": "stripe"}


def razorpay_body():
    return {"customer": CUSTOMER, "method": "online", "gateway": "razorpay"}


def webhook(ref, success=True, evtype="test.event"):
    return {"transaction_reference": ref, "success": success, "type": evtype}


@pytest.mark.asyncio
async def test_stripe_webhook_marks_successful(super_client, super_token, user_client):
    prod = await create_product(super_client, super_token, inventory=5)
    order = await user_client.post(
        f"/orders/{prod['id']}", params=TAX, json=stripe_body()
    )
    assert order.json()["order_status"] == "pending"

    resp = await user_client.post(
        "/payments/webhooks/stripe", json=webhook("test_pi_123", success=True)
    )
    assert resp.status_code == 200

    one = await user_client.get(f"/orders/{order.json()['id']}")
    body = one.json()
    assert body["order_status"] == "successful"
    # Payment isn't in OrderDetailResponse, so query items to confirm order exists.
    items = await user_client.get(f"/orders/{order.json()['id']}/items")
    assert items.status_code == 200


@pytest.mark.asyncio
async def test_webhook_failure_restocks(super_client, super_token, user_client):
    prod = await create_product(super_client, super_token, inventory=5)
    order = await user_client.post(
        f"/orders/{prod['id']}", params=TAX, json=stripe_body()
    )
    order_id = order.json()["id"]
    # Inventory decremented to 4 by the buy.
    assert (await user_client.get(f"/products/{prod['id']}")).json()["inventory"] == 4

    resp = await user_client.post(
        "/payments/webhooks/stripe", json=webhook("test_pi_123", success=False)
    )
    assert resp.status_code == 200

    one = await user_client.get(f"/orders/{order_id}")
    assert one.json()["order_status"] == "failed"
    # Inventory restocked back to 5.
    inv = (await user_client.get(f"/products/{prod['id']}")).json()["inventory"]
    assert inv == 5


@pytest.mark.asyncio
async def test_webhook_idempotent(super_client, super_token, user_client):
    prod = await create_product(super_client, super_token, inventory=5)
    order = await user_client.post(
        f"/orders/{prod['id']}", params=TAX, json=stripe_body()
    )
    order_id = order.json()["id"]

    # First webhook: failure -> failed + restock to 5.
    await user_client.post(
        "/payments/webhooks/stripe", json=webhook("test_pi_123", success=False)
    )
    assert (await user_client.get(f"/products/{prod['id']}")).json()["inventory"] == 5

    # Second webhook (duplicate delivery) must NOT restock again.
    await user_client.post(
        "/payments/webhooks/stripe", json=webhook("test_pi_123", success=False)
    )
    assert (await user_client.get(f"/products/{prod['id']}")).json()["inventory"] == 5
    assert (
        await user_client.get(f"/orders/{order_id}")
    ).json()["order_status"] == "failed"


@pytest.mark.asyncio
async def test_razorpay_webhook_success(super_client, super_token, user_client):
    prod = await create_product(super_client, super_token, inventory=5)
    order = await user_client.post(
        f"/orders/{prod['id']}", params=TAX, json=razorpay_body()
    )
    order_id = order.json()["id"]

    resp = await user_client.post(
        "/payments/webhooks/razorpay",
        json=webhook("test_rp_123", success=True),
    )
    assert resp.status_code == 200
    assert (
        await user_client.get(f"/orders/{order_id}")
    ).json()["order_status"] == "successful"


@pytest.mark.asyncio
async def test_webhook_unknown_reference_ignored(user_client):
    resp = await user_client.post(
        "/payments/webhooks/stripe",
        json=webhook("does_not_exist", success=True),
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
