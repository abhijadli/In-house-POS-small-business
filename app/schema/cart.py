from pydantic import BaseModel, ConfigDict


class ProductCartResponse(BaseModel):
    product_id: int
    quantity: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)
