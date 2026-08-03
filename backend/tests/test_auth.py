# backend/tests/test_auth.py
import pytest


@pytest.mark.asyncio
async def test_login_success(client, test_admin):
    """Test successful login."""
    response = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.ge",
        "password": "admin123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data["data"]
    assert "refresh_token" in data["data"]
    assert data["data"]["user"]["email"] == "admin@test.ge"


@pytest.mark.asyncio
async def test_login_wrong_password(client, test_admin):
    """Test login with wrong password."""
    response = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.ge",
        "password": "wrongpassword"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    """Test login with non-existent user."""
    response = await client.post("/api/v1/auth/login", json={
        "email": "nonexistent@test.ge",
        "password": "password123"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register(client):
    """Test user registration."""
    response = await client.post("/api/v1/auth/register", json={
        "company_name": "New Company",
        "full_name": "New User",
        "email": "newuser@test.ge",
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["user"]["email"] == "newuser@test.ge"
    assert data["data"]["user"]["role"] == "admin"
