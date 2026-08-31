from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from decimal import Decimal


class ProductCreate(BaseModel):
    name: str
    description: str | None = None
    price: Decimal = Field(gt=0)
    discount: Decimal = Field(ge=0)
    inventory: int


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str | None
    price: Decimal = Field(gt=0)
    discount: Decimal = Field(ge=0)
    inventory: int
    updated_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    discount: Decimal | None = Field(default=None, ge=0)
