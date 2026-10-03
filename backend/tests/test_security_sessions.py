"""P1.7 Security — failed login recorded, device parsing, sessions, revoke, audit log."""
import uuid

import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.security import LoginHistory
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_failed_login_unknown_email_not_recorded(client, test_company, caplog):
    r = await client.post("/api/v1/auth/login", json={"email": "no-such-user@demo.ge", "password": "wrong"})
    assert r.status_code == 401
    async with TestSessionLocal() as session:
        rows = (await session.execute(
            select(LoginHistory).where(
                LoginHistory.success.is_(False),
                LoginHistory.user_id.is_(None),
            )
        )).scalars().all()
        assert len(rows) == 0

    # The attempt is logged on app.audit.auth instead.
    assert any(
        record.levelname == "WARNING"
        and record.name == "app.audit.auth"
        and "failed login unknown email" in record.getMessage()
        for record in caplog.records
    )


async def test_failed_login_known_user_recorded(client, test_admin):
    r = await client.post("/api/v1/auth/login", json={"email": test_admin.email, "password": "wrong-password"})
    assert r.status_code == 401
    async with TestSessionLocal() as session:
        rows = (await session.execute(
            select(LoginHistory).where(
                LoginHistory.user_id == test_admin.id,
                LoginHistory.success.is_(False),
            )
        )).scalars().all()
        assert len(rows) >= 1
        h = rows[0]
        assert h.user_id == test_admin.id
        assert h.company_id == test_admin.company_id
        assert h.device_name is not None


async def test_login_records_device_and_session(client, auth_headers):
    # auth_headers fixture already performed a successful login
    async with TestSessionLocal() as session:
        rows = (await session.execute(
            select(LoginHistory).where(LoginHistory.success.is_(True)).order_by(LoginHistory.created_at.desc()).limit(1)
        )).scalars().all()
        assert len(rows) == 1
        h = rows[0]
        assert h.device_name is not None
        assert h.session_key is not None
        assert h.is_active is True


async def test_sessions_and_revoke(client, auth_headers):
    sess = await client.get("/api/v1/auth/sessions", headers=auth_headers)
    assert sess.status_code == 200, sess.text
    sessions = sess.json()["data"]
    assert len(sessions) >= 1
    sid = sessions[0]["id"]
    rev = await client.post(f"/api/v1/auth/sessions/{sid}/revoke", headers=auth_headers)
    assert rev.status_code == 200, rev.text
    assert rev.json()["data"]["revoked"] is True


async def test_logout_revokes_current(client, auth_headers):
    lg = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert lg.status_code == 200, lg.text
    assert lg.json()["data"]["logged_out"] is True


async def test_audit_log_entries(client, auth_headers):
    al = await client.get("/api/v1/auth/audit-logs", headers=auth_headers)
    assert al.status_code == 200, al.text
    assert isinstance(al.json()["data"], list)


async def test_audit_records_field_changes(client, auth_headers, test_company):
    """Editing a product records who/what/old/new in the audit log."""
    from sqlalchemy import select as sa_select
    from app.models.product import Product

    # create a product for this test
    p = await client.post("/api/v1/products/", json={
        "name": f"AuditTest-{uuid.uuid4().hex[:6]}", "sku": f"AU-{uuid.uuid4().hex[:6]}",
        "sale_price": 10, "purchase_price": 5, "min_stock": 3,
    }, headers=auth_headers)
    assert p.status_code in (200, 201), p.text
    pid = p.json()["data"]["id"]
    old_min = 3

    # change min_stock
    r = await client.patch(f"/api/v1/products/{pid}", json={"min_stock": 42}, headers=auth_headers)
    assert r.status_code == 200, r.text

    logs = await client.get(f"/api/v1/auth/audit-logs?entity_type=product", headers=auth_headers)
    assert logs.status_code == 200
    entries = logs.json()["data"]
    change = next((e for e in entries if e["entity_id"] == pid and e["field_name"] == "min_stock"), None)
    assert change is not None, "expected audit row for min_stock change"
    assert float(change["old_value"]) == float(old_min)
    assert float(change["new_value"]) == 42.0

    # cleanup
    await client.delete(f"/api/v1/products/{pid}", headers=auth_headers)


async def test_ua_parser():
    from app.services.ua_parser import parse_user_agent
    d = parse_user_agent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")
    assert "Chrome" in d["device_name"]
    assert d["os_name"] == "macOS"
    assert d["device_type"] == "desktop"

    m = parse_user_agent("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile Safari/604.1")
    assert m["device_type"] == "mobile"
    assert m["os_name"] == "iOS"

    b = parse_user_agent("curl/8.7.1")
    assert b["device_type"] == "bot"
    assert "curl" in b["device_name"].lower()
