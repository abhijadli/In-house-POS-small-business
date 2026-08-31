from abc import ABC, abstractmethod
import json
from app.schema.payments import (
    GatewayWebhookEvent,
    GatewayPaymentCreateResult,
    PaymentGateway,
)
from app.models.orders import PaymentDetails, Orders
from app.exception.payment_exception import GatewayNotImplementedError


class PaymentGatewayAdapter(ABC):
    @abstractmethod
    def create_payment(
        self, order: Orders, payment: PaymentDetails
    ) -> GatewayPaymentCreateResult: ...
    @abstractmethod
    def webhook_and_verify_payment(
        self, headers, raw_body: bytes
    ) -> GatewayWebhookEvent: ...


class StripeAdapter(PaymentGatewayAdapter):

    def create_payment(
        self, order: Orders, payment: PaymentDetails
    ) -> GatewayPaymentCreateResult:
        return GatewayPaymentCreateResult(
            transaction_reference="test_pi_123", client_secret="test_secret_abc"
        )

    def webhook_and_verify_payment(
        self, headers, raw_body: bytes
    ) -> GatewayWebhookEvent:
        payload = json.loads(raw_body)
        return GatewayWebhookEvent(
            transaction_reference=payload.get("transaction_reference", ""),
            success=payload.get("success", True),
            raw_type=payload.get("type", "test.event"),
        )


class RazorpayAdapter(PaymentGatewayAdapter):
    def create_payment(
        self, order: Orders, payment: PaymentDetails
    ) -> GatewayPaymentCreateResult:
        return GatewayPaymentCreateResult(
            transaction_reference="test_rp_123",
            checkout_url="https://checkout.razorpay.com/test",
        )

    def webhook_and_verify_payment(
        self, headers, raw_body: bytes
    ) -> GatewayWebhookEvent:
        payload = json.loads(raw_body)
        return GatewayWebhookEvent(
            transaction_reference=payload.get("transaction_reference", ""),
            success=payload.get("success", True),
            raw_type=payload.get("type", "test.event"),
        )


class BilldeskAdapter(PaymentGatewayAdapter):
    def create_payment(
        self, order: Orders, payment: PaymentDetails
    ) -> GatewayPaymentCreateResult:
        raise GatewayNotImplementedError()

    def webhook_and_verify_payment(
        self, headers, raw_body: bytes
    ) -> GatewayWebhookEvent:
        raise GatewayNotImplementedError()

# Factory to select payment gateway as per input
class PaymentGatewayFactory:
    @staticmethod
    def get(gateway: PaymentGateway) -> PaymentGatewayAdapter:
        match gateway:
            case PaymentGateway.STRIPE:
                return StripeAdapter()
            case PaymentGateway.RAZORPAY:
                return RazorpayAdapter()
            case PaymentGateway.BILLDESK:
                return BilldeskAdapter()
            case PaymentGateway.CASH:
                raise ValueError("Cash payments do not use a gateway adapter")
            case _:
                raise GatewayNotImplementedError()
