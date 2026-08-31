from app.db.session import Base
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta


class ProductCart(Base):
    __tablename__ = "product_cart"
    product_id = Column(Integer, ForeignKey("products.id"), primary_key=True)
    quantity = Column(Integer, nullable=False, default=1)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    inserted_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    # Column to be used in case of autocleanup of cart
    expires_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.utcnow() + timedelta(minutes=30),
    )

    products = relationship("Products", back_populates="cart_items")
    user = relationship("Users", back_populates="cart_items")
