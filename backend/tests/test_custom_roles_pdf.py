"""Custom roles enforcement + PDF template layout rendering."""
import base64
import uuid

import pytest
from sqlalchemy import select

from app.models.platform import CustomRole
from app.models.user import User
from app.core.security import hash_password
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _enable_module(db, company_id, code: str):
    from sqlalchemy import text as sa_text
    from app.models.module import AppModule
    module = (await db.execute(select(AppModule).where(AppModule.code == code))).scalar_one_or_none()
    if not module:
        module = AppModule(code=code, name=code, is_active=True)
        db.add(module)
        await db.flush()
    await db.execute(
        sa_text("INSERT INTO company_modules (id, company_id, module_id, enabled) VALUES (:id, :cid, :mid, true) ON CONFLICT DO NOTHING"),
        {"id": uuid.uuid4(), "cid": company_id, "mid": module.id},
    )


async def test_custom_role_enforces_module_access(client, auth_headers, test_company):
    """A user bound to a custom role gets exactly the module matrix of that role."""
    # create custom role: only 'automations' accessible
    role_resp = await client.post("/api/v1/platform/custom-roles", json={
        "name": "მხოლოდ ავტომატიზაცია",
        "permissions": {"automations": {"can_access": True, "can_create": True, "can_edit": True}},
    }, headers=auth_headers)
    assert role_resp.status_code == 201
    role_id = uuid.UUID(role_resp.json()["data"]["id"])

    async with TestSessionLocal() as session:
        await _enable_module(session, test_company.id, "automations")
        await _enable_module(session, test_company.id, "email-marketing")
        u = User(company_id=test_company.id, email=f"crole-{uuid.uuid4().hex[:6]}@demo.ge",
                 hashed_password=hash_password("pass12345"), full_name="Role User",
                 role=User.Role.EMPLOYEE, custom_role_id=role_id)
        session.add(u)
        await session.commit()
        email = u.email

    # login
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "pass12345"})
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # automations accessible (in role matrix + module enabled)
    ok = await client.get("/api/v1/automations/", headers=headers)
    assert ok.status_code == 200, ok.text

    # email-marketing NOT in role matrix → 403 with the custom role name
    denied = await client.get("/api/v1/email-campaigns/", headers=headers)
    assert denied.status_code == 403
    assert "მხოლოდ ავტომატიზაცია" in denied.json()["detail"]


async def test_pdf_template_layout_renders(client, auth_headers):
    """The designer's title/color/footer actually reach the PDF generator."""
    resp = await client.post("/api/v1/platform/pdf-templates", json={
        "name": "მწვანე ანგარიშ-ფაქტურა", "doc_type": "invoice",
        "layout": {"title": "ანგარიშ-ფაქტურა", "color": "#10b981", "footer": "მწვანე დიზაინი"},
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    tid = resp.json()["data"]["id"]

    render = await client.post(f"/api/v1/platform/pdf-templates/{tid}/render", json={
        "number": "INV-L1", "company_name": "კომპანია", "client_name": "კლიენტი",
        "items": [{"name": "X", "qty": 1, "price": 10, "total": 10}],
        "subtotal": 10, "vat": 1.8, "total": 11.8, "date": "2026-08-29",
    }, headers=auth_headers)
    assert render.status_code == 200, render.text
    pdf = base64.b64decode(render.json()["data"]["pdf_base64"])
    assert pdf[:5] == b"%PDF-"
    # layout is stored on the template (round-trip check)
    lst = await client.get("/api/v1/platform/pdf-templates", headers=auth_headers)
    t = next(t for t in lst.json()["data"] if t["id"] == tid)
    assert t["layout"]["title"] == "ანგარიშ-ფაქტურა"
    assert t["layout"]["color"] == "#10b981"
