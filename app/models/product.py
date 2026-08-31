from app.db.session import Base
from sqlalchemy import (
    Integer,
    String,
    Boolean,
    DateTime,
    Column,
    Numeric,
    CheckConstraint,
)
from datetime import datetime
from sqlalchemy.orm import relationship


class Products(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(String(255), nullable=True, default=None)
    price = Column(Numeric(10, 2), nullable=False)
    discount = Column(Numeric(10, 2), nullable=False)
    inventory = Column(Integer, nullable=False, default=0)
    is_deleted = Column(Boolean, nullable=False, default=False)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "inventory >= 0",
            name="check_inventory_non_negative",
        ),
    )

    order_items = relationship("OrderItems", back_populates="product")
    cart_items = relationship("ProductCart", back_populates="products")