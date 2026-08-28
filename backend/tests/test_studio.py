"""No-code Studio — apps, forms with fields, records with required validation."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _create_app(client, auth_headers) -> str:
    resp = await client.post("/api/v1/studio/apps", json={
        "name": f"HR Requests-{uuid.uuid4().hex[:4]}",
        "description": "შვებულების მოთხოვნები",
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def test_studio_app_crud(client, auth_headers):
    app_id = await _create_app(client, auth_headers)

    lst = await client.get("/api/v1/studio/apps", headers=auth_headers)
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1

    upd = await client.patch(f"/api/v1/studio/apps/{app_id}", json={"name": "Renamed"}, headers=auth_headers)
    assert upd.status_code == 200, upd.text

    rem = await client.delete(f"/api/v1/studio/apps/{app_id}", headers=auth_headers)
    assert rem.status_code == 200, rem.text
    lst2 = await client.get("/api/v1/studio/apps", headers=auth_headers)
    assert len(lst2.json()["data"]) == 0


async def test_studio_form_with_fields_and_records(client, auth_headers):
    app_id = await _create_app(client, auth_headers)

    form = await client.post(f"/api/v1/studio/apps/{app_id}/forms", json={
        "name": "შვებულების მოთხოვნა",
        "fields": [
            {"label": "თანამშრომელი", "field_type": "text", "required": True},
            {"label": "დღეების რაოდენობა", "field_key": "days", "field_type": "number", "required": True},
            {"label": "კომენტარი", "field_type": "textarea"},
        ],
    }, headers=auth_headers)
    assert form.status_code == 201, form.text
    form_id = form.json()["data"]["id"]

    forms = await client.get(f"/api/v1/studio/apps/{app_id}/forms", headers=auth_headers)
    assert forms.status_code == 200
    fdata = forms.json()["data"]
    assert len(fdata) == 1
    assert len(fdata[0]["fields"]) == 3
    assert fdata[0]["fields"][0]["required"] is True

    # missing required field → 422
    bad = await client.post(f"/api/v1/studio/forms/{form_id}/records", json={
        "data": {"days": 5},
    }, headers=auth_headers)
    assert bad.status_code == 422

    # valid record
    ok = await client.post(f"/api/v1/studio/forms/{form_id}/records", json={
        "data": {"თანამშრომელი": "ნინო", "days": 5, "კომენტარი": "ოჯახური"},
    }, headers=auth_headers)
    assert ok.status_code == 201, ok.text

    recs = await client.get(f"/api/v1/studio/forms/{form_id}/records", headers=auth_headers)
    assert recs.status_code == 200
    assert recs.json()["data"]["total"] == 1
    assert recs.json()["data"]["items"][0]["data"]["days"] == 5


async def test_studio_record_delete(client, auth_headers):
    app_id = await _create_app(client, auth_headers)
    form = await client.post(f"/api/v1/studio/apps/{app_id}/forms", json={
        "name": "მარტივი ფორმა",
        "fields": [{"label": "სახელი", "required": True}],
    }, headers=auth_headers)
    form_id = form.json()["data"]["id"]

    rec = await client.post(f"/api/v1/studio/forms/{form_id}/records", json={
        "data": {"სახელი": "გიორგი"},
    }, headers=auth_headers)
    rec_id = rec.json()["data"]["id"]

    rem = await client.delete(f"/api/v1/studio/records/{rec_id}", headers=auth_headers)
    assert rem.status_code == 200, rem.text

    recs = await client.get(f"/api/v1/studio/forms/{form_id}/records", headers=auth_headers)
    assert recs.json()["data"]["total"] == 0
