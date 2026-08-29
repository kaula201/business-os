"""Georgian counterparty verification — SRS open-data (data.rs.ge) client.

The Revenue Service publishes open datasets (VAT payers registry, taxpayer
registry). This client tries the documented endpoints; when the open-data
portal is unreachable it raises CounterpartyUnreachable so the caller can
record an honest "unreachable" status instead of a fabricated result.
"""
from __future__ import annotations

from typing import Any

import httpx

SRS_OPEN_DATA_BASE = "https://data.rs.ge"
VAT_PAYERS_PATH = "/api/v1/vat-payers"  # documented open-data endpoint


class CounterpartyUnreachable(RuntimeError):
    pass


class SrsOpenDataClient:
    def __init__(self, base_url: str = SRS_OPEN_DATA_BASE, timeout: float = 12.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def check_vat_payer(self, identification_code: str) -> dict[str, Any]:
        """Look up a VAT-payer record by identification code.

        Returns {"found": bool, "is_vat_payer": bool, "name": str|None,
                 "registration_date": str|None, "raw": dict|None}.
        Raises CounterpartyUnreachable when the portal cannot be reached.
        """
        url = f"{self.base_url}{VAT_PAYERS_PATH}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params={"identification_code": identification_code})
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CounterpartyUnreachable("SRS ღია მონაცემების პორტალი მიუწვდომელია") from exc

        # Normalize: the registry may return a list or a single object
        items = payload if isinstance(payload, list) else payload.get("data", payload.get("items", []))
        if isinstance(items, dict):
            items = [items]
        for item in items or []:
            code = str(item.get("identification_code") or item.get("tin") or item.get("id") or "")
            if code == identification_code:
                return {
                    "found": True,
                    "is_vat_payer": bool(item.get("is_vat_payer", item.get("vat_payer", True))),
                    "name": item.get("name") or item.get("legal_name"),
                    "registration_date": item.get("registration_date") or item.get("registered_at"),
                    "raw": item,
                }
        return {"found": False, "is_vat_payer": False, "name": None, "registration_date": None, "raw": None}
