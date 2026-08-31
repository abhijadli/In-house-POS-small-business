import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import Base, get_db
from app.models.user import Users, UserRole

# --- Guard: the test suite must never touch the real database. ---
if not settings.test_database_url:
    raise RuntimeError(
        "TEST_DATABASE_URL is not set; refusing to run the test suite."
    )
if settings.test_database_url == settings.database_url:
    raise RuntimeError(
        "TEST_DATABASE_URL must differ from DATABASE_URL; the test suite "
        "drops and recreates every table it touches."
    )

engine_test = create_async_engine(settings.test_database_url, poolclass=NullPool)
AsyncSessionLocalTest = async_sessionmaker(engine_test, expire_on_commit=False)

# Import every model so Base.metadata is fully populated.
import app.models.user  # noqa: F401, E402
import app.models.product  # noqa: F401, E402
import app.models.cart  # noqa: F401, E402
import app.models.orders  # noqa: F401, E402
import app.core.refresh_token_model  # noqa: F401, E402

from main import app  # noqa: E402


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def client():
    """An async HTTP client bound to the FastAPI app, using the test DB."""

    async def _override_get_db():
        async with AsyncSessionLocalTest() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="session", autouse=True)
async def _create_tables():
    """Create all tables once for the test session, drop them at the end."""
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    """Reset all tables and reseed base users before every test."""
    async with engine_test.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE users, products, orders, order_items, "
                "payment_details, product_cart, refresh_tokens "
                "RESTART IDENTITY CASCADE"
            )
        )
    async with AsyncSession(engine_test) as session:
        session.add(
            Users(
                username="superadmin",
                hashed_password=hash_password("pass123"),
                role=UserRole.SUPERADMIN,
            )
        )
        session.add(
            Users(
                username="user1",
                hashed_password=hash_password("pass123"),
                role=UserRole.USER,
            )
        )
        await session.commit()
    yield


@pytest_asyncio.fixture
async def super_token(client):
    resp = await client.post(
        "/users/login", json={"username": "superadmin", "password": "pass123"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def user_token(client):
    resp = await client.post(
        "/users/login", json={"username": "user1", "password": "pass123"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def super_client(client, super_token):
    client.headers.update(auth_header(super_token))
    return client


@pytest_asyncio.fixture
async def user_client(client, user_token):
    client.headers.update(auth_header(user_token))
    return client


async def create_product(client, token, **overrides):
    payload = {
        "name": "Widget",
        "description": "A widget",
        "price": 100.00,
        "discount": 10.00,
        "inventory": 5,
    }
    payload.update(overrides)
    resp = await client.post(
        "/products",
        json=payload,
        headers=auth_header(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()
