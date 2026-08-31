from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db
from app.schema.orders import PaymentGateway
from app.schema.payments import GatewayWebhookEvent
from app.services.payments import PaymentGatewayFactory
from app.services.orders import apply_webhook_event

payment_router = APIRouter()


@payment_router.post(
    "/webhooks/stripe",
    status_code=status.HTTP_200_OK,
    summary="Stripe payment webhook (public, no JWT)",
)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()
    adapter = PaymentGatewayFactory.get(PaymentGateway.STRIPE)
    event: GatewayWebhookEvent = adapter.webhook_and_verify_payment(
        request.headers, raw_body
    )
    await apply_webhook_event(db, event)
    return {"status": "ok"}


@payment_router.post(
    "/webhooks/razorpay",
    status_code=status.HTTP_200_OK,
    summary="Razorpay payment webhook (public, no JWT)",
)
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()
    adapter = PaymentGatewayFactory.get(PaymentGateway.RAZORPAY)
    event: GatewayWebhookEvent = adapter.webhook_and_verify_payment(
        request.headers, raw_body
    )
    await apply_webhook_event(db, event)
    return {"status": "ok"}
