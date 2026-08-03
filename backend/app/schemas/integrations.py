from typing import Any

from pydantic import BaseModel


class RSGeStatusResponse(BaseModel):
    configured: bool
    reachable: bool
    authenticated: bool
    server_time: str | None = None


class RSWaybillResponse(BaseModel):
    waybill_number: str
    data: dict[str, Any]
