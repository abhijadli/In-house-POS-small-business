from enum import Enum
from app.db.session import Base
from datetime import datetime
from app.schema.orders import OrderStatus, PaymentMethod, PaymentGateway
from app.schema.payments import PaymentStatus
from sqlalchemy import (
    Enum as SqlalchemyEnum,
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship


class Orders(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_status = Column(
        SqlalchemyEnum(OrderStatus), default=OrderStatus.PENDING, nullable=False
    )
    total_items = Column(Integer, nullable=False, default=1)
    subtotal = Column(Numeric(10, 2), nullable=False)
    discount = Column(Numeric(10, 2), nullable=False)
    tax = Column(Numeric(10, 2), nullable=False)
    grand_total = Column(Numeric(10, 2), nullable=False)
    customer_name = Column(String, nullable=True, default=None)
    customer_mobile = Column(String, nullable=False)
    customer_email = Column(String, nullable=True)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("Users", back_populates="orders")
    order_items = relationship("OrderItems", back_populates="order")
    payment_detail = relationship(
        "PaymentDetails", back_populates="order", uselist=False
    )


class OrderItems(Base):
    __tablename__ = "order_items"

    order_id = Column(
        Integer,
        ForeignKey("orders.id"),
        nullable=False,
        primary_key=True,
    )
    product_id = Column(
        Integer,
        ForeignKey("products.id"),
        nullable=False,
        primary_key=True,
    )
    product_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False)
    discount = Column(Numeric(10, 2), nullable=False)
    net_price = Column(Numeric(10, 2), nullable=False)
    tax = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)

    # backpopulates
    order = relationship("Orders", back_populates="order_items")
    product = relationship("Products", back_populates="order_items")


class PaymentDetails(Base):
    __tablename__ = "payment_details"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    transaction_reference = Column(String, default=None)
    gateway = Column(SqlalchemyEnum(PaymentGateway), nullable=False)
    method = Column(SqlalchemyEnum(PaymentMethod), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(
        SqlalchemyEnum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False
    )
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    order = relationship("Orders", back_populates="payment_detail")
