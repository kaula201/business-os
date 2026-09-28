"""Go-live security checks: JWT defaults, CORS, webhook HMAC, logout, 2FA, SSRF, paths."""
import hashlib
import hmac
import json

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.core.storage_paths import UnsafeStoragePath, allocate_helpdesk_path, resolve_storage_path
from app.core.totp import current_totp, verify_totp
from app.core.url_safety import UnsafeWebhookURL, assert_public_webhook_url
from app.main import app


def test_jwt_secret_rejects_empty_and_known_defaults(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("APP_ENV", "development")
    for bad in ("", "jwt-secret-change-me", "change-me-in-production"):
        monkeypatch.setenv("JWT_SECRET_KEY", bad)
        with pytest.raises(ValidationError):
            Settings()


def test_production_jwt_must_be_long(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "unique-but-short-key")
    with pytest.raises(ValidationError):
        Settings()
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 32)
    loaded = Settings()
    assert loaded.is_production() is True
    assert loaded.allows_demo_seed() is False


def test_cors_wildcard_refused_and_runtime_allowlist_has_no_star(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 40)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(ValidationError):
        Settings()

    origins = []
    for layer in app.user_middleware:
        if getattr(layer.cls, "__name__", "") == "CORSMiddleware":
            origins = layer.kwargs.get("allow_origins") or []
            assert layer.kwargs.get("allow_credentials") is True
    assert origins, "CORS middleware allowlist was not configured"
    assert "*" not in origins


def test_demo_seed_only_in_development(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("APP_ENV", "development")
    assert Settings().allows_demo_seed() is True
    monkeypatch.setenv("APP_ENV", "test")
    assert Settings().allows_demo_seed() is False
    monkeypatch.setenv("APP_ENV", "production")
    assert Settings().allows_demo_seed() is False


def test_webhook_url_blocks_private_and_metadata(monkeypatch):
    previous_env = settings.APP_ENV
    previous_allow = settings.WEBHOOK_URL_ALLOWLIST
    try:
        settings.APP_ENV = "production"
        settings.WEBHOOK_URL_ALLOWLIST = ""
        for blocked in (
            "http://169.254.169.254/latest/meta-data",
            "http://10.1.2.3/hook",
            "http://192.168.1.10/hook",
            "http://127.0.0.1/hook",
            "http://localhost/hook",
            "http://metadata.google.internal/computeMetadata/v1/",
            "file:///etc/passwd",
        ):
            with pytest.raises(UnsafeWebhookURL):
                assert_public_webhook_url(blocked)
        assert assert_public_webhook_url("http://1.1.1.1/hook") == "http://1.1.1.1/hook"

        settings.WEBHOOK_URL_ALLOWLIST = "1.1.1.1"
        assert_public_webhook_url("http://1.1.1.1/hook")
        with pytest.raises(UnsafeWebhookURL):
            assert_public_webhook_url("http://8.8.8.8/hook")

        settings.APP_ENV = "test"
        settings.WEBHOOK_URL_ALLOWLIST = ""
        assert_public_webhook_url("http://127.0.0.1:9/hook")
        with pytest.raises(UnsafeWebhookURL):
            assert_public_webhook_url("http://10.0.0.8/hook")
    finally:
        settings.APP_ENV = previous_env
        settings.WEBHOOK_URL_ALLOWLIST = previous_allow


def test_helpdesk_attachment_path_stays_in_storage_root(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    path = allocate_helpdesk_path("11111111-1111-1111-1111-111111111111", "../../etc/passwd.pdf")
    assert path.is_relative_to(tmp_path / "helpdesk")
    assert path.suffix == ".pdf"
    assert ".." not in path.name
    assert not str(path).startswith("/app")
    path.write_bytes(b"%PDF")


def test_storage_path_rejects_escape(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    root_file = tmp_path / "documents" / "ok.txt"
    root_file.parent.mkdir(parents=True)
    root_file.write_text("ok")
    assert resolve_storage_path(str(root_file)).name == "ok.txt"
    with pytest.raises(UnsafeStoragePath):
        resolve_storage_path("/etc/passwd")
    with pytest.raises(UnsafeStoragePath):
        resolve_storage_path("../../../../etc/passwd")


async def test_logout_rejects_same_access_token(client, test_admin):
    login = await client.post("/api/v1/auth/login", json={
        "email": test_admin.email, "password": "admin123",
    })
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = await client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200, me.text

    out = await client.post("/api/v1/auth/logout", headers=headers)
    assert out.status_code == 200, out.text

    again = await client.get("/api/v1/users/me", headers=headers)
    assert again.status_code == 401, again.text


async def test_revoked_session_rejects_access_token(client, test_admin):
    login = await client.post("/api/v1/auth/login", json={
        "email": test_admin.email, "password": "admin123",
    })
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    sessions = await client.get("/api/v1/auth/sessions", headers=headers)
    assert sessions.status_code == 200, sessions.text
    session_id = sessions.json()["data"][0]["id"]
    revoked = await client.post(f"/api/v1/auth/sessions/{session_id}/revoke", headers=headers)
    assert revoked.status_code == 200, revoked.text
    again = await client.get("/api/v1/users/me", headers=headers)
    assert again.status_code == 401, again.text


async def test_saas_webhook_requires_hmac_outside_sandbox(client, test_company):
    previous_env = settings.APP_ENV
    previous_secret = settings.SAAS_WEBHOOK_SECRET
    body = json.dumps({
        "company_id": str(test_company.id),
        "event": "payment_succeeded",
        "payment_reference": "sbx_security",
    }).encode()
    try:
        settings.APP_ENV = "production"
        settings.SAAS_WEBHOOK_SECRET = ""
        missing = await client.post(
            "/api/v1/saas/webhook",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert missing.status_code == 401, missing.text

        settings.SAAS_WEBHOOK_SECRET = "whsec_test_secret"
        bad = await client.post(
            "/api/v1/saas/webhook",
            content=body,
            headers={"Content-Type": "application/json", "X-Saas-Signature": "deadbeef"},
        )
        assert bad.status_code == 401, bad.text

        signature = hmac.new(b"whsec_test_secret", body, hashlib.sha256).hexdigest()
        accepted = await client.post(
            "/api/v1/saas/webhook",
            content=body,
            headers={"Content-Type": "application/json", "X-Saas-Signature": signature},
        )
        # Signature passed; this company has no subscription row.
        assert accepted.status_code == 404, accepted.text
    finally:
        settings.APP_ENV = previous_env
        settings.SAAS_WEBHOOK_SECRET = previous_secret


async def test_production_hides_docs_and_open_register(client):
    previous = settings.APP_ENV
    try:
        settings.APP_ENV = "production"
        for path in ("/docs", "/redoc", "/openapi.json"):
            response = await client.get(path)
            assert response.status_code == 404, path
        registered = await client.post("/api/v1/auth/register", json={
            "company_name": "Blocked Co",
            "full_name": "Blocked User",
            "email": "blocked@test.ge",
            "password": "password123",
        })
        assert registered.status_code == 403, registered.text
    finally:
        settings.APP_ENV = previous

    docs = await client.get("/openapi.json")
    assert docs.status_code == 200


async def test_reset_password_uses_body_not_query(client):
    via_query = await client.post(
        "/api/v1/auth/reset-password",
        params={"token": "abc", "new_password": "password123"},
    )
    assert via_query.status_code == 422, via_query.text
    via_body = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "not-a-real-token", "new_password": "password123"},
    )
    assert via_body.status_code == 400, via_body.text


async def test_document_upload_rejects_arbitrary_path(client, auth_headers):
    escaped = await client.post("/api/v1/documents/", json={
        "title": "secret",
        "filename": "passwd",
        "file_path": "/etc/passwd",
    }, headers=auth_headers)
    assert escaped.status_code == 400, escaped.text

    uploaded = await client.post(
        "/api/v1/documents/upload",
        data={"title": "Note", "document_type": "other"},
        files={"file": ("note.txt", b"hello storage", "text/plain")},
        headers=auth_headers,
    )
    assert uploaded.status_code == 201, uploaded.text
    stored = uploaded.json()["data"]["file_path"]
    assert "/etc/" not in stored
    assert "documents" in stored.replace("\\", "/")


async def test_login_requires_totp_when_enabled(client, test_admin):
    login = await client.post("/api/v1/auth/login", json={
        "email": test_admin.email, "password": "admin123",
    })
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    setup = await client.post("/api/v1/auth/2fa/setup", headers=headers)
    assert setup.status_code == 200, setup.text
    secret = setup.json()["data"]["secret"]
    assert setup.json()["data"]["enabled"] is False
    assert verify_totp(secret, current_totp(secret))

    still_open = await client.post("/api/v1/auth/login", json={
        "email": test_admin.email, "password": "admin123",
    })
    assert still_open.status_code == 200, still_open.text

    confirmed = await client.post(
        "/api/v1/auth/2fa/confirm",
        json={"code": current_totp(secret)},
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["enabled"] is True

    missing = await client.post("/api/v1/auth/login", json={
        "email": test_admin.email, "password": "admin123",
    })
    assert missing.status_code == 401, missing.text
    assert "აუცილებელია" in missing.json()["detail"]

    wrong_code = "000000" if current_totp(secret) != "000000" else "111111"
    wrong = await client.post("/api/v1/auth/login", json={
        "email": test_admin.email, "password": "admin123", "totp_code": wrong_code,
    })
    assert wrong.status_code == 401, wrong.text

    ok = await client.post("/api/v1/auth/login", json={
        "email": test_admin.email, "password": "admin123", "totp_code": current_totp(secret),
    })
    assert ok.status_code == 200, ok.text
