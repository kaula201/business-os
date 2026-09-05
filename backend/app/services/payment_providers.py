"""Payment provider adapters — TBC Pay / BOG Pay / fiscal device.

Real integration is activated when the merchant credentials are present in the
environment (TBC_MERCHANT_ID / TBC_SECRET_KEY / BOG_CLIENT_ID / BOG_SECRET_KEY).
Without credentials the adapter runs in sandbox mode and returns a deterministic
authorized response — the same pattern used for RS.ge and Stripe.

Each adapter exposes:
    charge(amount, currency, reference) -> dict(status, provider_ref, raw)
    refund(provider_ref, amount)          -> dict(status, provider_ref)
    check_status(provider_ref)            -> dict(status)
"""
import hashlib
import hmac
import json
import uuid
from decimal import Decimal
from typing import Any

from app.core.config import settings


class PaymentProviderError(Exception):
    pass


class BaseProvider:
    provider: str = "base"

    def __init__(self) -> None:
        self.sandbox = True

    def _ref(self) -> str:
        return f"{self.provider}-{uuid.uuid4().hex[:12].upper()}"

    async def charge(self, amount: Decimal, currency: str = "GEL", reference: str | None = None) -> dict[str, Any]:
        raise NotImplementedError

    async def refund(self, provider_ref: str, amount: Decimal) -> dict[str, Any]:
        raise NotImplementedError

    async def check_status(self, provider_ref: str) -> dict[str, Any]:
        raise NotImplementedError


class TBCProvider(BaseProvider):
    """TBC Pay — real integration via TBC merchant API when credentials are set."""

    provider = "tbc"

    def __init__(self) -> None:
        super().__init__()
        self.merchant_id = settings.TBC_MERCHANT_ID
        self.secret_key = settings.TBC_SECRET_KEY
        self.sandbox = not (self.merchant_id and self.secret_key)

    async def charge(self, amount: Decimal, currency: str = "GEL", reference: str | None = None) -> dict[str, Any]:
        if self.sandbox:
            return {
                "status": "authorized",
                "provider_ref": self._ref(),
                "raw": {"mode": "sandbox", "merchant": self.merchant_id or "demo"},
            }
        # Real TBC Pay API call (production credentials required)
        import httpx
        payload = {
            "amount": float(amount),
            "currency": currency,
            "merchant_id": self.merchant_id,
            "order_id": reference or self._ref(),
        }
        signature = hmac.new(
            self.secret_key.encode(), json.dumps(payload, sort_keys=True).encode(), hashlib.sha256
        ).hexdigest()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.tbcbank.ge/v1/payments/charge",
                    json=payload, headers={"X-Signature": signature},
                )
                resp.raise_for_status()
                data = resp.json()
                return {"status": "authorized", "provider_ref": data.get("id"), "raw": data}
        except Exception as e:
            raise PaymentProviderError(f"TBC charge failed: {e}") from e

    async def refund(self, provider_ref: str, amount: Decimal) -> dict[str, Any]:
        if self.sandbox:
            return {"status": "refunded", "provider_ref": provider_ref, "raw": {"mode": "sandbox"}}
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"https://api.tbcbank.ge/v1/payments/{provider_ref}/refund",
                    json={"amount": float(amount)},
                )
                resp.raise_for_status()
                return {"status": "refunded", "provider_ref": provider_ref, "raw": resp.json()}
        except Exception as e:
            raise PaymentProviderError(f"TBC refund failed: {e}") from e

    async def check_status(self, provider_ref: str) -> dict[str, Any]:
        if self.sandbox:
            return {"status": "authorized", "provider_ref": provider_ref}
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(f"https://api.tbcbank.ge/v1/payments/{provider_ref}")
                resp.raise_for_status()
                data = resp.json()
                return {"status": data.get("status", "unknown"), "provider_ref": provider_ref, "raw": data}
        except Exception as e:
            raise PaymentProviderError(f"TBC status check failed: {e}") from e


class BOGProvider(BaseProvider):
    """BOG Pay — real integration via BOG API when credentials are set."""

    provider = "bog"

    def __init__(self) -> None:
        super().__init__()
        self.client_id = settings.BOG_CLIENT_ID
        self.secret_key = settings.BOG_SECRET_KEY
        self.sandbox = not (self.client_id and self.secret_key)

    async def charge(self, amount: Decimal, currency: str = "GEL", reference: str | None = None) -> dict[str, Any]:
        if self.sandbox:
            return {
                "status": "authorized",
                "provider_ref": self._ref(),
                "raw": {"mode": "sandbox", "client": self.client_id or "demo"},
            }
        import httpx
        payload = {
            "amount": float(amount),
            "currency": currency,
            "client_id": self.client_id,
            "order_id": reference or self._ref(),
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.bog.ge/payments/v1/charge", json=payload,
                    headers={"Authorization": f"Bearer {self.secret_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
                return {"status": "authorized", "provider_ref": data.get("id"), "raw": data}
        except Exception as e:
            raise PaymentProviderError(f"BOG charge failed: {e}") from e

    async def refund(self, provider_ref: str, amount: Decimal) -> dict[str, Any]:
        if self.sandbox:
            return {"status": "refunded", "provider_ref": provider_ref, "raw": {"mode": "sandbox"}}
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"https://api.bog.ge/payments/v1/{provider_ref}/refund",
                    json={"amount": float(amount)},
                    headers={"Authorization": f"Bearer {self.secret_key}"},
                )
                resp.raise_for_status()
                return {"status": "refunded", "provider_ref": provider_ref, "raw": resp.json()}
        except Exception as e:
            raise PaymentProviderError(f"BOG refund failed: {e}") from e

    async def check_status(self, provider_ref: str) -> dict[str, Any]:
        if self.sandbox:
            return {"status": "authorized", "provider_ref": provider_ref}
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"https://api.bog.ge/payments/v1/{provider_ref}",
                    headers={"Authorization": f"Bearer {self.secret_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
                return {"status": data.get("status", "unknown"), "provider_ref": provider_ref, "raw": data}
        except Exception as e:
            raise PaymentProviderError(f"BOG status check failed: {e}") from e


class FiscalDevice:
    """Certified fiscal printer integration (Georgia: fiscal receipt).

    Real integration requires the device driver/credentials in the environment
    (FISCAL_DEVICE_URL / FISCAL_DEVICE_TOKEN). Without them the receipt is
    generated in sandbox mode with a deterministic fiscal number.
    """

    def __init__(self) -> None:
        self.device_url = settings.FISCAL_DEVICE_URL
        self.device_token = settings.FISCAL_DEVICE_TOKEN
        self.sandbox = not (self.device_url and self.device_token)

    async def print_receipt(self, receipt: dict) -> dict[str, Any]:
        """Send a fiscal receipt to the certified device."""
        if self.sandbox:
            return {
                "fiscal_number": f"FISCAL-{uuid.uuid4().hex[:10].upper()}",
                "status": "printed",
                "raw": {"mode": "sandbox"},
            }
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.device_url}/receipts",
                    json=receipt, headers={"Authorization": f"Bearer {self.device_token}"},
                )
                resp.raise_for_status()
                data = resp.json()
                return {"fiscal_number": data.get("fiscal_number"), "status": "printed", "raw": data}
        except Exception as e:
            raise PaymentProviderError(f"Fiscal device failed: {e}") from e


def get_provider(provider: str) -> BaseProvider:
    if provider == "tbc":
        return TBCProvider()
    if provider == "bog":
        return BOGProvider()
    raise PaymentProviderError(f"უცნობი provider: {provider}")
