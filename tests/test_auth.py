import pytest

from conftest import auth_header


@pytest.mark.asyncio
async def test_login_seeded_superadmin(client):
    resp = await client.post(
        "/users/login", json={"username": "superadmin", "password": "pass123"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["refresh_token"]


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    resp = await client.post(
        "/users/login",
        json={"username": "superadmin", "password": "wrongpass"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_requires_token(client):
    resp = await client.get("/products")
    # HTTPBearer -> 403 when no credentials provided
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_register_requires_super(client, user_token):
    # A plain USER may not register new users.
    resp = await client.post(
        "/users",
        json={"username": "newuser", "password": "pass123"},
        headers=auth_header(user_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_register_new_user_then_login(client, super_token):
    resp = await client.post(
        "/users",
        json={"username": "newuser", "password": "pass123"},
        headers=auth_header(super_token),
    )
    assert resp.status_code == 201
    assert resp.json()["username"] == "newuser"

    login = await client.post(
        "/users/login", json={"username": "newuser", "password": "pass123"}
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


@pytest.mark.asyncio
async def test_register_duplicate_username(client, super_token):
    resp = await client.post(
        "/users",
        json={"username": "superadmin", "password": "pass123"},
        headers=auth_header(super_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_password_too_short(client, super_token):
    resp = await client.post(
        "/users",
        json={"username": "shortpwuser", "password": "123"},
        headers=auth_header(super_token),
    )
    assert resp.status_code == 422
