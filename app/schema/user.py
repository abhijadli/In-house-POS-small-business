from pydantic import BaseModel, Field, ConfigDict
from app.models.user import UserRole
from datetime import datetime


class UserCreate(BaseModel):
    username: str
    password: str = Field(min_length=6)
    # Defaulting user role as only users will be created as per business logic.
    # role : UserRole = UserRole.USER


class PasswordUpdate(BaseModel):
    username: str
    new_password: str = Field(min_length=6)


class UserResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)
