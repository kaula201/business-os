"""CRM Excel export."""
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.crm import CRMLead, CRMOpportunity, CRMActivity
from app.schemas.common import ResponseBase
from io import BytesIO
import openpyxl
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/crm", tags=["CRM — ექსპორტი"])


@router.get("/export/leads")
async def export_leads(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("crm", "can_access")),
):
    filters = [CRMLead.company_id == current_user.company_id]
    if status:
        filters.append(CRMLead.status == status)
    rows = (await db.execute(
        select(CRMLead).where(*filters).order_by(CRMLead.created_at.desc())
    )).scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ლიდები"
    ws.append(["კომპანია", "საკონტაქტო პირი", "ტელეფონი", "ელფოსტა", "წყარო", "სტატუსი", "სავარაუდო ღირებულება", "შექმნის თარიღი"])
    for r in rows:
        ws.append([r.company_name, r.contact_name, r.phone, r.email, r.source, r.status, float(r.estimated_value), str(r.created_at)])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=crm_leads.xlsx"})


@router.get("/export/opportunities")
async def export_opportunities(
    stage: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("crm", "can_access")),
):
    filters = [CRMOpportunity.company_id == current_user.company_id]
    if stage:
        filters.append(CRMOpportunity.stage == stage)
    rows = (await db.execute(
        select(CRMOpportunity).where(*filters).order_by(CRMOpportunity.updated_at.desc())
    )).scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Opportunities"
    ws.append(["სახელი", "ეტაპი", "თანხა", "ალბათობა", "მოსალოდნელი დახურვა", "შექმნის თარიღი"])
    for r in rows:
        ws.append([r.name, r.stage, float(r.amount), r.probability, str(r.expected_close_date or ""), str(r.created_at)])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=crm_opportunities.xlsx"})
