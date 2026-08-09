"""Tests for inventory valuation (weighted average cost layers)."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.cost_layer import ProductCostLayer
from app.models.product import Product
from app.services.inventory_valuation import (
    apply_incoming_movement,
    apply_outgoing_movement,
    ensure_layer,
    get_valuation,
)
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_product(test_company, purchase_price=10.0) -> str:
    async with TestSessionLocal() as session:
        product = Product(
            company_id=test_company.id,
            sku=f"VAL-{uuid.uuid4().hex[:6]}",
            name="Valuation Product",
            sale_price=30,
            purchase_price=purchase_price,
            current_stock=0,
        )
        session.add(product)
        await session.commit()
        return str(product.id)


# ── Weighted average math ────────────────────────────────────────────────────


async def test_weighted_average_recomputes_on_incoming(test_company):
    pid = uuid.UUID(await _make_product(test_company))
    async with TestSessionLocal() as session:
        layer = await apply_incoming_movement(session, test_company.id, pid, Decimal("10"), Decimal("10"))
        assert layer.quantity_remaining == Decimal("10")
        assert layer.weighted_avg_cost == Decimal("10.0000")

        # second incoming at different price → new weighted average
        layer = await apply_incoming_movement(session, test_company.id, pid, Decimal("10"), Decimal("20"))
        assert layer.quantity_remaining == Decimal("20")
        assert layer.weighted_avg_cost == Decimal("15.0000")  # (10*10 + 10*20)/20


async def test_outgoing_uses_current_average(test_company):
    pid = uuid.UUID(await _make_product(test_company))
    async with TestSessionLocal() as session:
        await apply_incoming_movement(session, test_company.id, pid, Decimal("10"), Decimal("10"))
        await apply_incoming_movement(session, test_company.id, pid, Decimal("10"), Decimal("20"))

        layer, cogs = await apply_outgoing_movement(session, test_company.id, pid, Decimal("5"))
        assert layer.quantity_remaining == Decimal("15")
        assert cogs == Decimal("75.00")  # 5 * 15.00
        assert layer.weighted_avg_cost == Decimal("15.0000")  # unchanged on outflow


async def test_valuation_totals(test_company):
    pid = uuid.UUID(await _make_product(test_company))
    async with TestSessionLocal() as session:
        await apply_incoming_movement(session, test_company.id, pid, Decimal("10"), Decimal("10"))
        await apply_incoming_movement(session, test_company.id, pid, Decimal("10"), Decimal("20"))
        result = await get_valuation(session, test_company.id, pid)
    assert result["quantity"] == 20.0
    assert result["weighted_avg_cost"] == 15.0
    assert result["total_value"] == 300.0


async def test_layer_defaults_to_purchase_price(test_company):
    pid = uuid.UUID(await _make_product(test_company, purchase_price=12.5))
    async with TestSessionLocal() as session:
        layer = await ensure_layer(session, test_company.id, pid)
        assert layer.weighted_avg_cost == Decimal("12.5000")
        assert layer.quantity_remaining == Decimal("0")


# ── API ───────────────────────────────────────────────────────────────────────


async def test_valuation_api_adjust_and_get(client, auth_headers, test_company):
    pid = await _make_product(test_company)

    adjust = await client.post("/api/v1/inventory/valuation/adjust", json={
        "product_id": pid, "quantity": "10", "unit_cost": "10",
    }, headers=auth_headers)
    assert adjust.status_code == 200, adjust.text
    assert adjust.json()["weighted_avg_cost"] == 10.0
    assert adjust.json()["total_value"] == 100.0

    get = await client.get(f"/api/v1/inventory/valuation/{pid}", headers=auth_headers)
    assert get.status_code == 200
    assert get.json()["quantity"] == 10.0


async def test_valuation_api_tenant_scoped(client, auth_headers, test_company):
    # Unknown product id in this company → 404 (not a stray layer)
    resp = await client.get(f"/api/v1/inventory/valuation/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404
