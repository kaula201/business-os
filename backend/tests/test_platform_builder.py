"""Configurable platform: custom fields, workflows, reports, import mappings, industry templates."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def test_custom_field_crud_and_values(client, auth_headers, test_company, db_session):
    # create field
    resp = await client.post("/api/v1/platform/custom-fields", json={
        "entity_type": "client", "name": "tax_regime", "label_ka": "საგადასახადო რეჟიმი",
        "label_en": "Tax regime", "field_type": "select", "options": ["ზოგადი", "მცირე ბიზნესი"],
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    field_id = resp.json()["data"]["id"]

    # invalid entity rejected
    bad = await client.post("/api/v1/platform/custom-fields", json={
        "entity_type": "nonsense", "name": "x", "label_ka": "X",
    }, headers=auth_headers)
    assert bad.status_code == 422

    # set value on a record
    entity_id = uuid.uuid4()
    setv = await client.put(f"/api/v1/platform/custom-values/client/{entity_id}", json={
        field_id: "ზოგადი",
    }, headers=auth_headers)
    assert setv.status_code == 200, setv.text
    assert setv.json()["data"]["saved"] == 1

    # read back (query params style)
    vals = await client.get(
        f"/api/v1/platform/custom-values?entity_type=client&entity_id={entity_id}",
        headers=auth_headers,
    )
    assert vals.status_code == 200
    assert any(v["field_id"] == field_id for v in vals.json()["data"])

    # delete
    dele = await client.delete(f"/api/v1/platform/custom-fields/{field_id}", headers=auth_headers)
    assert dele.status_code == 200


async def test_workflow_crud(client, auth_headers):
    resp = await client.post("/api/v1/platform/workflows", json={
        "entity_type": "order", "name": "გაყიდვების ვორქფლოუ",
        "steps": [
            {"order": 1, "name": "დამტკიცება", "status_from": "draft", "status_to": "confirmed", "required_role": "manager"},
            {"order": 2, "name": "შიპინგი", "status_from": "confirmed", "status_to": "shipping", "required_role": None},
        ],
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    wf_id = resp.json()["data"]["id"]

    lst = await client.get("/api/v1/platform/workflows", headers=auth_headers)
    assert lst.status_code == 200
    assert any(w["id"] == wf_id for w in lst.json()["data"])

    dele = await client.delete(f"/api/v1/platform/workflows/{wf_id}", headers=auth_headers)
    assert dele.status_code == 200


async def test_report_export_csv(client, auth_headers, test_company):
    # need a client row for the export
    from app.models.client import Client
    from tests.conftest import TestSessionLocal
    async with TestSessionLocal() as session:
        session.add(Client(company_id=test_company.id, name="Report Client",
                           client_type="legal", identification_code="REP-1", status="active"))
        await session.commit()

    resp = await client.post("/api/v1/platform/reports", json={
        "name": "კლიენტები", "entity_type": "client",
        "columns": [{"key": "name", "label": "სახელი"}, {"key": "status", "label": "სტატუსი"}],
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    rid = resp.json()["data"]["id"]

    ex = await client.get(f"/api/v1/platform/reports/{rid}/export", headers=auth_headers)
    assert ex.status_code == 200, ex.text
    data = ex.json()["data"]
    assert data["filename"] == "კლიენტები.csv"
    assert "Report Client" in data["csv"]
    assert data["row_count"] >= 1


async def test_industry_templates(client, auth_headers):
    # create one via the endpoint (test DB has no seeds)
    resp = await client.post("/api/v1/platform/industry-templates", json={
        "slug": "retail", "name_ka": "საცალო ვაჭრობა", "name_en": "Retail",
        "modules": ["pos", "inventory"],
        "custom_fields": [{"entity_type": "product", "name": "supplier_ref", "label_ka": "მომწოდებლის კოდი", "field_type": "text"}],
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text

    # duplicate slug rejected
    dup = await client.post("/api/v1/platform/industry-templates", json={
        "slug": "retail", "name_ka": "X",
    }, headers=auth_headers)
    assert dup.status_code == 409

    lst = await client.get("/api/v1/platform/industry-templates", headers=auth_headers)
    assert lst.status_code == 200
    assert any(t["slug"] == "retail" for t in lst.json()["data"])


async def test_import_mapping_crud(client, auth_headers):
    resp = await client.post("/api/v1/platform/import-mappings", json={
        "entity_type": "client", "name": "CSV კლიენტები",
        "mapping": {"A": "name", "B": "identification_code"},
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    mid = resp.json()["data"]["id"]

    lst = await client.get("/api/v1/platform/import-mappings", headers=auth_headers)
    assert any(m["id"] == mid for m in lst.json()["data"])

    dele = await client.delete(f"/api/v1/platform/import-mappings/{mid}", headers=auth_headers)
    assert dele.status_code == 200


async def test_pdf_template_render(client, auth_headers):
    """PDF template designer: create template, render a real PDF."""
    import base64

    resp = await client.post("/api/v1/platform/pdf-templates", json={
        "name": "ინვოისი სტანდარტი", "doc_type": "invoice",
        "layout": {"title": "ინვოისი", "color": "#2563eb"},
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    tid = resp.json()["data"]["id"]

    render = await client.post(f"/api/v1/platform/pdf-templates/{tid}/render", json={
        "number": "INV-T1", "company_name": "ტესტ კომპანია", "company_id_code": "T-1",
        "client_name": "კლიენტი", "items": [{"name": "პროდუქტი", "qty": 1, "price": 100, "total": 100}],
        "subtotal": 100, "vat": 18, "total": 118, "date": "2026-08-29",
    }, headers=auth_headers)
    assert render.status_code == 200, render.text
    data = render.json()["data"]
    assert data["filename"] == "ინვოისი.pdf"
    assert data["bytes"] > 1000
    pdf = base64.b64decode(data["pdf_base64"])
    assert pdf[:5] == b"%PDF-"

    dele = await client.delete(f"/api/v1/platform/pdf-templates/{tid}", headers=auth_headers)
    assert dele.status_code == 200


async def test_custom_role_crud(client, auth_headers):
    resp = await client.post("/api/v1/platform/custom-roles", json={
        "name": "მაღაზიის მენეჯერი",
        "permissions": {"pos": {"can_access": True, "can_create": True}, "inventory": {"can_access": True}},
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    rid = resp.json()["data"]["id"]

    upd = await client.patch(f"/api/v1/platform/custom-roles/{rid}", json={
        "permissions": {"pos": {"can_access": True, "can_create": True, "can_edit": True}},
    }, headers=auth_headers)
    assert upd.status_code == 200

    lst = await client.get("/api/v1/platform/custom-roles", headers=auth_headers)
    assert any(r["id"] == rid for r in lst.json()["data"])

    dele = await client.delete(f"/api/v1/platform/custom-roles/{rid}", headers=auth_headers)
    assert dele.status_code == 200
