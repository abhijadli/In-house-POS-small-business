from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
from datetime import datetime
from decimal import Decimal


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCESSFUL = "successful"
    FAILED = "failed"


class PaymentMethod(str, Enum):
    ONLINE = "online"
    CASH = "cash"


class PaymentGateway(str, Enum):
    RAZORPAY = "razorpay"
    STRIPE = "stripe"
    BILLDESK = "billdesk"
    CASH = "cash"


class PaymentDetailResponse(BaseModel):
    id: int
    order_id: int
    transaction_reference: str | None = None
    gateway: PaymentGateway
    method: PaymentMethod
    amount: Decimal = Field(gt=0)
    status: PaymentStatus
    updated_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GatewayPaymentCreateResult(BaseModel):
    transaction_reference: str  # provider's payment id (e.g. "pi_3O...")
    client_secret: str | None = None  # Stripe
    checkout_url: str | None = None  # Razorpay


class GatewayWebhookEvent(BaseModel):
    transaction_reference: str  # provider's payment id from the event
    success: bool  # True = paid, False = failed
    raw_type: str
