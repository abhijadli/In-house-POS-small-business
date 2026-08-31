from pydantic_settings import BaseSettings, SettingsConfigDict

"""
holds setting

BaseSettings — a Pydantic model that automatically reads matching environment variables 
(case-insensitive, so DATABASE_URL in .env maps to database_url here)
Each field is typed — if access_token_expire_minutes isn't a valid int, 
this crashes at import time, not when someone logs in at 2am
SettingsConfigDict(env_file=".env") tells it where to load from
settings = Settings() — a single instance you import elsewhere as from app.core.config import settings
"""


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 3
    # Optional so the app still boots in environments that never run tests.
    # conftest.py refuses to run without it, and refuses to run if it matches
    # database_url - the test suite drops and recreates every table it touches.
    test_database_url: str | None = None
    # Payment gateway values
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    razorpay_webhook_secret: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()   # pyright: ignore[reportCallIssue]
