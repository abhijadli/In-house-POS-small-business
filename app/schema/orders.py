from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    EmailStr,
    field_validator,
    model_validator,
)
from enum import Enum
from datetime import datetime
from decimal import Decimal
import phonenumbers
from app.schema.payments import PaymentGateway, PaymentMethod, PaymentDetailResponse


class OrderStatus(str, Enum):
    PENDING = "pending"
    SUCCESSFUL = "successful"
    FAILED = "failed"


class CustomerDetails(BaseModel):
    name: str | None = None
    mobile: str
    email: EmailStr | None = None

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, value: str) -> str:
        try:
            number = phonenumbers.parse(value, "IN")

            if not phonenumbers.is_valid_number(number):
                raise ValueError("Invalid mobile number")

            return value

        except phonenumbers.NumberParseException:
            raise ValueError("Invalid mobile number")


class OrderRequest(BaseModel):
    customer: CustomerDetails
    method: PaymentMethod
    gateway: PaymentGateway | None = None

    @model_validator(mode="after")
    def check_gateway_matches_method(self) -> OrderRequest:
        # if method == ONLINE: gateway must be STRIPE or RAZORPAY
        # if method == CASH:    gateway must be None
        if self.method == PaymentMethod.CASH:
            if self.gateway is not None:
                raise ValueError(
                    "Invalid Payment gateway. Gateway must be null for cash entries."
                )
        elif self.method == PaymentMethod.ONLINE:
            if self.gateway not in (PaymentGateway.RAZORPAY, PaymentGateway.STRIPE):
                raise ValueError(
                    "Invalid Payment gateway. Choose from the available ones only."
                )
        return self


class OrderDetailResponse(BaseModel):
    id: int
    user_id: int
    order_status: OrderStatus
    total_items: int
    subtotal: Decimal = Field(gt=0)
    discount: Decimal = Field(ge=0)
    tax: Decimal = Field(ge=0)
    grand_total: Decimal = Field(gt=0)
    customer_name: str | None = None
    customer_mobile: str
    customer_email: str | None = None
    updated_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderItemResponse(BaseModel):
    order_id: int
    product_id: int
    product_name: str
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0)
    discount: Decimal = Field(ge=0)
    net_price: Decimal = Field(gt=0)
    tax: Decimal = Field(ge=0)
    total_price: Decimal = Field(gt=0)

    model_config = ConfigDict(from_attributes=True)


class OrderCreateResponse(BaseModel):
    id: int
    user_id: int
    order_status: OrderStatus
    total_items: int
    subtotal: Decimal = Field(gt=0)
    discount: Decimal = Field(ge=0)
    tax: Decimal = Field(ge=0)
    grand_total: Decimal = Field(gt=0)
    customer_name: str | None = None
    customer_mobile: str
    customer_email: str | None = None
    updated_at: datetime
    created_at: datetime
    payment: PaymentDetailResponse = Field(validation_alias="payment_detail")
    gateway_client: dict | None = None

    model_config = ConfigDict(from_attributes=True)
