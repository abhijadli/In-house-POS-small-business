import pytest

from app.core.security import create_access_token, decode_access_token
from app.exception.payment_exception import GatewayNotImplementedError
from app.scheduler import start_scheduler, stop_scheduler
from app.schema.payments import PaymentGateway
from app.services.payments import BilldeskAdapter, PaymentGatewayFactory
from app.services.product import ProductImportError, _parse_product_rows
import app.jobs.my_job as job_mod


def test_decode_access_token_invalid():
    assert decode_access_token("not-a-jwt") is None


def test_decode_access_token_valid_round_trip():
    token = create_access_token(user_id=42, token_version=3)
    assert decode_access_token(token) == (42, 3)


def test_payment_factory_billdesk_not_implemented():
    adapter = PaymentGatewayFactory.get(PaymentGateway.BILLDESK)
    with pytest.raises(GatewayNotImplementedError):
        adapter.create_payment(None, None)


def test_payment_factory_cash_rejected():
    with pytest.raises(ValueError, match="Cash payments"):
        PaymentGatewayFactory.get(PaymentGateway.CASH)


def test_billdesk_adapter_raises_not_implemented():
    with pytest.raises(GatewayNotImplementedError):
        BilldeskAdapter().create_payment(None, None)


def test_billdesk_webhook_raises_not_implemented():
    with pytest.raises(GatewayNotImplementedError):
        BilldeskAdapter().webhook_and_verify_payment({}, b"{}")


def test_parse_product_rows_rejects_missing_worksheet(monkeypatch):
    class FakeWorkbook:
        active = None

    monkeypatch.setattr(
        "app.services.product.load_workbook",
        lambda **kwargs: FakeWorkbook(),
    )

    with pytest.raises(ProductImportError, match="at least one worksheet"):
        _parse_product_rows(b"fake")


@pytest.mark.asyncio
async def test_scheduler_start_and_stop():
    start_scheduler()
    stop_scheduler()


@pytest.mark.asyncio
async def test_job_logs_and_continues_when_empty_cart_raises(
    monkeypatch, super_client, super_token, user_client
):
    from datetime import datetime, timedelta

    from sqlalchemy import update

    from conftest import AsyncSessionLocalTest, create_product
    from app.models.cart import ProductCart

    prod = await create_product(super_client, super_token, inventory=5)
    await user_client.post(f"/cart/{prod['id']}/add_product")

    async with AsyncSessionLocalTest() as db:
        await db.execute(
            update(ProductCart)
            .where(ProductCart.product_id == prod["id"])
            .values(expires_at=datetime.utcnow() - timedelta(minutes=5))
        )
        await db.commit()

    async def failing_empty_cart(db, user_id):
        raise RuntimeError("forced failure")

    monkeypatch.setattr(job_mod, "empty_cart_for_user", failing_empty_cart)
    job_mod.SessionLocal = AsyncSessionLocalTest

    await job_mod.my_job()

    cart = await user_client.get("/cart")
    assert len(cart.json()) == 1
