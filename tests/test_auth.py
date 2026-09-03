import pytest

from conftest import auth_header


@pytest.mark.asyncio
async def test_login_unknown_username(client):
    resp = await client.post(
        "/users/login",
        json={"username": "nobody", "password": "pass123"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_success(client):
    login = await client.post(
        "/users/login", json={"username": "superadmin", "password": "pass123"}
    )
    refresh_token = login.json()["refresh_token"]

    resp = await client.post(
        "/users/refresh", json={"refresh_token": refresh_token}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_refresh_token_invalid(client):
    resp = await client.post(
        "/users/refresh", json={"refresh_token": "not-a-real-token"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid Refresh Token."


@pytest.mark.asyncio
async def test_logout_success(client):
    login = await client.post(
        "/users/login", json={"username": "superadmin", "password": "pass123"}
    )
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/users/logout", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert resp.json() == "Successfully logged out."

    refresh = await client.post(
        "/users/refresh", json={"refresh_token": refresh_token}
    )
    assert refresh.status_code == 401


@pytest.mark.asyncio
async def test_logout_invalid_token(client):
    resp = await client.post(
        "/users/logout", json={"refresh_token": "not-a-real-token"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invalid_jwt_token_rejected(client):
    resp = await client.get(
        "/products",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid JWT token."


@pytest.mark.asyncio
async def test_stale_access_token_after_password_change(client, super_token):
    login = await client.post(
        "/users/login", json={"username": "user1", "password": "pass123"}
    )
    old_token = login.json()["access_token"]

    update = await client.patch(
        "/users/password",
        json={"username": "user1", "new_password": "newpass123"},
        headers=auth_header(super_token),
    )
    assert update.status_code == 202

    resp = await client.get("/products", headers=auth_header(old_token))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_password_success(client, super_token):
    resp = await client.patch(
        "/users/password",
        json={"username": "user1", "new_password": "changed123"},
        headers=auth_header(super_token),
    )
    assert resp.status_code == 202
    assert resp.json()["username"] == "user1"

    login = await client.post(
        "/users/login", json={"username": "user1", "password": "changed123"}
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_update_password_user_not_found(client, super_token):
    resp = await client.patch(
        "/users/password",
        json={"username": "missing-user", "new_password": "changed123"},
        headers=auth_header(super_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_password_admin_cannot_change_superadmin(
    client, super_token, user_token
):
    promote = await client.post(
        "/users",
        json={"username": "admin1", "password": "pass123"},
        headers=auth_header(super_token),
    )
    admin_id = promote.json()["id"]
    await client.patch(
        f"/users/{admin_id}",
        headers=auth_header(super_token),
    )

    admin_login = await client.post(
        "/users/login", json={"username": "admin1", "password": "pass123"}
    )
    admin_token = admin_login.json()["access_token"]

    resp = await client.patch(
        "/users/password",
        json={"username": "superadmin", "new_password": "hacked123"},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_make_user_admin(client, super_token):
    created = await client.post(
        "/users",
        json={"username": "future-admin", "password": "pass123"},
        headers=auth_header(super_token),
    )
    user_id = created.json()["id"]

    resp = await client.patch(
        f"/users/{user_id}",
        headers=auth_header(super_token),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_make_user_admin_forbidden_for_regular_user(client, user_token):
    resp = await client.patch(
        "/users/2",
        headers=auth_header(user_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_make_user_admin_not_found(client, super_token):
    resp = await client.patch(
        "/users/9999",
        headers=auth_header(super_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_user_success(client, super_token):
    created = await client.post(
        "/users",
        json={"username": "deleteme", "password": "pass123"},
        headers=auth_header(super_token),
    )
    user_id = created.json()["id"]

    resp = await client.delete(
        f"/users/{user_id}",
        headers=auth_header(super_token),
    )
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_delete_user_not_found(client, super_token):
    resp = await client.delete(
        "/users/9999",
        headers=auth_header(super_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_superadmin_forbidden(client, super_token):
    resp = await client.delete(
        "/users/1",
        headers=auth_header(super_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_admin_requires_superadmin(client, super_token):
    created = await client.post(
        "/users",
        json={"username": "admin2", "password": "pass123"},
        headers=auth_header(super_token),
    )
    admin_id = created.json()["id"]
    await client.patch(f"/users/{admin_id}", headers=auth_header(super_token))

    another = await client.post(
        "/users",
        json={"username": "admin3", "password": "pass123"},
        headers=auth_header(super_token),
    )
    admin3_id = another.json()["id"]
    await client.patch(f"/users/{admin3_id}", headers=auth_header(super_token))

    admin_login = await client.post(
        "/users/login", json={"username": "admin2", "password": "pass123"}
    )
    admin_token = admin_login.json()["access_token"]

    resp = await client.delete(
        f"/users/{admin3_id}",
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_self_forbidden_for_admin(client, super_token):
    created = await client.post(
        "/users",
        json={"username": "admin4", "password": "pass123"},
        headers=auth_header(super_token),
    )
    admin_id = created.json()["id"]
    await client.patch(f"/users/{admin_id}", headers=auth_header(super_token))

    admin_login = await client.post(
        "/users/login", json={"username": "admin4", "password": "pass123"}
    )
    admin_token = admin_login.json()["access_token"]

    resp = await client.delete(
        f"/users/{admin_id}",
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 403


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
