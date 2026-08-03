"""External government integrations."""
from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import ResponseBase
from app.schemas.integrations import RSGeStatusResponse, RSWaybillResponse
from app.services.rs_ge import RSGeClient, RSGeError

router = APIRouter(prefix="/integrations", tags=["ინტეგრაციები"])


def require_finance_role(user: User) -> None:
    if user.role not in {User.Role.ADMIN, User.Role.ACCOUNTANT}:
        raise HTTPException(status_code=403, detail="ინტეგრაციებზე წვდომის უფლება არ გაქვთ")


def rs_client() -> RSGeClient:
    return RSGeClient(settings.RS_WAYBILL_URL, settings.RS_SERVICE_USER, settings.RS_SERVICE_PASSWORD)


@router.get("/rs/status", response_model=ResponseBase[RSGeStatusResponse])
async def rs_status(current_user: User = Depends(get_current_user)):
    require_finance_role(current_user)
    configured = bool(settings.RS_SERVICE_USER and settings.RS_SERVICE_PASSWORD)
    client = rs_client()
    try:
        server_time = await client.get_server_time()
        authenticated = await client.check_service_user() if configured else False
    except RSGeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ResponseBase(data=RSGeStatusResponse(
        configured=configured,
        reachable=True,
        authenticated=authenticated,
        server_time=server_time,
    ))


@router.get("/rs/waybills/{waybill_number}", response_model=ResponseBase[RSWaybillResponse])
async def get_rs_waybill(waybill_number: str, current_user: User = Depends(get_current_user)):
    require_finance_role(current_user)
    if not settings.RS_SERVICE_USER or not settings.RS_SERVICE_PASSWORD:
        raise HTTPException(status_code=503, detail="RS.ge service user credentials არ არის დაყენებული")
    try:
        data = await rs_client().get_waybill_by_number(waybill_number)
    except RSGeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ResponseBase(data=RSWaybillResponse(waybill_number=waybill_number, data=data))
