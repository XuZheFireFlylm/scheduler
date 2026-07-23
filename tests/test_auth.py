"""Tests for auth module."""
import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "Str0ngPass!",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"
    assert "id" in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient, test_user: User):
    resp = await client.post("/api/v1/auth/register", json={
        "username": "testuser",
        "email": "another@example.com",
        "password": "Str0ngPass!",
    })
    assert resp.status_code == 409
    assert resp.json()["detail"] == "username_already_taken"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_user: User):
    resp = await client.post("/api/v1/auth/register", json={
        "username": "anotheruser",
        "email": "test@example.com",
        "password": "Str0ngPass!",
    })
    assert resp.status_code == 409
    assert resp.json()["detail"] == "email_already_registered"


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "username": "validuser",
        "email": "not-an-email",
        "password": "Str0ngPass!",
    })
    assert resp.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user: User):
    resp = await client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "TestPass123!",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user: User):
    resp = await client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "WrongPassword!",
    })
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_username_or_password"


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "username": "doesnotexist",
        "password": "AnyPassword!",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient, auth_headers: dict, test_user: User):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testuser"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 403  # HTTPBearer default error
