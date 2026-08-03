import pytest

from app.api.v1.endpoints import integrations
from app.core.config import settings


@pytest.mark.asyncio
async def test_rs_status_reports_reachable_but_unconfigured(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "RS_SERVICE_USER", "")
    monkeypatch.setattr(settings, "RS_SERVICE_PASSWORD", "")

    async def fake_server_time(self):
        return "2026-07-29T12:00:00"

    monkeypatch.setattr(integrations.RSGeClient, "get_server_time", fake_server_time)
    response = await client.get("/api/v1/integrations/rs/status", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"] == {
        "configured": False,
        "reachable": True,
        "authenticated": False,
        "server_time": "2026-07-29T12:00:00",
    }


@pytest.mark.asyncio
async def test_rs_waybill_requires_credentials(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "RS_SERVICE_USER", "")
    monkeypatch.setattr(settings, "RS_SERVICE_PASSWORD", "")
    response = await client.get("/api/v1/integrations/rs/waybills/TEST-001", headers=auth_headers)
    assert response.status_code == 503
    assert "credentials" in response.json()["detail"]


@pytest.mark.asyncio
async def test_rs_waybill_uses_configured_service_user(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "RS_SERVICE_USER", "service-user")
    monkeypatch.setattr(settings, "RS_SERVICE_PASSWORD", "secret")

    async def fake_waybill(self, number):
        assert self.service_user == "service-user"
        assert self.service_password == "secret"
        assert number == "WB-100"
        return {"ID": "123", "STATUS": "1"}

    monkeypatch.setattr(integrations.RSGeClient, "get_waybill_by_number", fake_waybill)
    response = await client.get("/api/v1/integrations/rs/waybills/WB-100", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"]["data"] == {"ID": "123", "STATUS": "1"}
