from app.db.session import Base
from enum import Enum
from sqlalchemy import Column, Integer, Boolean, String, DateTime, Index, text
from sqlalchemy import Enum as SQLAlchemyEnum
from datetime import datetime
from sqlalchemy.orm import relationship


class UserRole(str, Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    USER = "user"


# Roles having super priviliges
SUPER_ROLES = {UserRole.ADMIN, UserRole.SUPERADMIN}


class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(
        SQLAlchemyEnum(UserRole),
        default=UserRole.USER,
        nullable=False,
    )
    is_deleted = Column(Boolean, nullable=False, default=False)
    access_token_version = Column(Integer, nullable=False, default=0)
    updated_date = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_date = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index(
            "uq_users_username_active",
            "username",
            unique=True,
            postgresql_where=text("is_deleted IS FALSE"),
        ),
    )

    orders = relationship("Orders", back_populates="user")
    cart_items = relationship("ProductCart", back_populates="user")
    refresh_tokens = relationship(
        "RefreshTokens",
        back_populates="user",
        cascade="all, delete-orphan",
    )
