from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.api.v1.endpoints import currency as currency_endpoint
from app.services.nbg_rates import seconds_until_next_run


@pytest.mark.asyncio
async def test_nbg_sync_normalizes_quantities_is_bidirectional_and_idempotent(
    client, auth_headers, monkeypatch,
):
    async def fake_fetch_nbg_rates(rate_date: date | None = None):
        assert rate_date == date(2026, 7, 1)
        return {
            "date": "2026-07-01T00:00:00.000Z",
            "currencies": [
                {"code": "USD", "quantity": 1, "rate": 2.7},
                {"code": "AMD", "quantity": 1000, "rate": 7.2},
            ],
        }

    monkeypatch.setattr(currency_endpoint, "fetch_nbg_rates", fake_fetch_nbg_rates)

    first = await client.post(
        "/api/v1/currency/rates/sync-nbg?rate_date=2026-07-01",
        headers=auth_headers,
    )
    assert first.status_code == 200
    assert first.json()["data"] == {
        "rate_date": "2026-07-01",
        "currencies_received": 2,
        "rates_created": 4,
        "rates_updated": 0,
    }

    second = await client.post(
        "/api/v1/currency/rates/sync-nbg?rate_date=2026-07-01",
        headers=auth_headers,
    )
    assert second.status_code == 200
    assert second.json()["data"]["rates_created"] == 0
    assert second.json()["data"]["rates_updated"] == 4

    rates_response = await client.get("/api/v1/currency/rates", headers=auth_headers)
    assert rates_response.status_code == 200
    rates = rates_response.json()["data"]
    by_pair = {(row["from_currency"], row["to_currency"]): row for row in rates}
    assert by_pair[("USD", "GEL")]["rate"] == pytest.approx(2.7)
    assert by_pair[("GEL", "USD")]["rate"] == pytest.approx(0.37037)
    assert by_pair[("AMD", "GEL")]["rate"] == pytest.approx(0.0072)
    assert by_pair[("GEL", "AMD")]["rate"] == pytest.approx(138.888889)
    assert all(row["source"] == "nbg" for row in rates)

    converted = await client.post(
        "/api/v1/currency/convert",
        headers=auth_headers,
        json={
            "amount": 100,
            "from_currency": "USD",
            "to_currency": "GEL",
            "rate_date": "2026-07-01",
        },
    )
    assert converted.status_code == 200
    assert converted.json()["data"]["converted_amount"] == 270.0

    status = await client.get("/api/v1/currency/rates/nbg-status", headers=auth_headers)
    assert status.status_code == 200
    status_data = status.json()["data"]
    assert status_data["enabled"] is True
    assert status_data["schedule"] == "18:05"
    assert status_data["timezone"] == "Asia/Tbilisi"
    assert status_data["status"] == "success"
    assert status_data["trigger"] == "manual"
    assert status_data["effective_date"] == "2026-07-01"
    assert status_data["rates_updated"] == 4


def test_nbg_scheduler_calculates_next_tbilisi_run():
    tz = ZoneInfo("Asia/Tbilisi")
    before = datetime(2026, 7, 29, 18, 0, tzinfo=tz)
    after = datetime(2026, 7, 29, 18, 10, tzinfo=tz)
    assert seconds_until_next_run(before) == 5 * 60
    assert seconds_until_next_run(after) == (23 * 60 + 55) * 60
