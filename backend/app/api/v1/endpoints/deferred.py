"""Deferred revenue/expense API with monthly GL recognition."""
import calendar
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.time import utc_now
from app.models.deferred import DeferredRecognition, DeferredSchedule
from app.models.gl import GLAccount
from app.models.user import User
from app.schemas.common import ResponseBase
from app.schemas.deferred import DeferredRecognitionResponse, DeferredScheduleCreate, DeferredScheduleResponse, RecognizeDueRequest
from app.services.gl_posting import post_journal_entry

router = APIRouter(prefix="/deferred", tags=["გადავადებული ოპერაციები"])

def add_months(value: date, months: int) -> date:
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))

def money(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def require_role(user: User):
    if user.role not in {User.Role.ADMIN, User.Role.ACCOUNTANT}:
        raise HTTPException(403, "გადავადებულ ოპერაციებზე წვდომის უფლება არ გაქვთ")

async def load_schedule(db: AsyncSession, company_id: UUID, schedule_id: UUID):
    return (await db.execute(select(DeferredSchedule).options(selectinload(DeferredSchedule.recognitions)).where(DeferredSchedule.id==schedule_id, DeferredSchedule.company_id==company_id))).scalar_one_or_none()

async def serialize(db: AsyncSession, schedule: DeferredSchedule) -> DeferredScheduleResponse:
    accounts=(await db.execute(select(GLAccount).where(GLAccount.id.in_([schedule.source_gl_account_id,schedule.recognition_gl_account_id])))).scalars().all()
    amap={a.id:a for a in accounts}; source=amap[schedule.source_gl_account_id]; target=amap[schedule.recognition_gl_account_id]
    recognized=sum((money(r.amount) for r in schedule.recognitions if r.status=="recognized"),Decimal("0"))
    return DeferredScheduleResponse(id=schedule.id,company_id=schedule.company_id,name=schedule.name,deferral_type=schedule.deferral_type,total_amount=float(schedule.total_amount),recognized_amount=float(recognized),remaining_amount=float(money(schedule.total_amount)-recognized),start_date=schedule.start_date,periods=schedule.periods,source_gl_account_id=source.id,source_gl_account_code=source.code,source_gl_account_name=source.name,recognition_gl_account_id=target.id,recognition_gl_account_code=target.code,recognition_gl_account_name=target.name,status=schedule.status,notes=schedule.notes,created_at=schedule.created_at,recognitions=[DeferredRecognitionResponse(id=r.id,period_no=r.period_no,recognition_date=r.recognition_date,amount=float(r.amount),status=r.status,journal_entry_id=r.journal_entry_id,recognized_at=r.recognized_at) for r in schedule.recognitions])

@router.get("/schedules",response_model=ResponseBase[list[DeferredScheduleResponse]])
async def list_schedules(current_user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_role(current_user)
    rows=(await db.execute(select(DeferredSchedule).options(selectinload(DeferredSchedule.recognitions)).where(DeferredSchedule.company_id==current_user.company_id).order_by(DeferredSchedule.created_at.desc()))).scalars().all()
    return ResponseBase(data=[await serialize(db,s) for s in rows])

@router.post("/schedules",response_model=ResponseBase[DeferredScheduleResponse],status_code=201)
async def create_schedule(payload:DeferredScheduleCreate,current_user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_role(current_user)
    accounts=(await db.execute(select(GLAccount).where(GLAccount.company_id==current_user.company_id,GLAccount.id.in_([payload.source_gl_account_id,payload.recognition_gl_account_id]),GLAccount.is_active.is_(True)))).scalars().all()
    if len({a.id for a in accounts})!=2: raise HTTPException(400,"ორივე GL ანგარიში უნდა იყოს აქტიური და ეკუთვნოდეს კომპანიას")
    amap={a.id:a for a in accounts}; source=amap[payload.source_gl_account_id]; target=amap[payload.recognition_gl_account_id]
    if payload.deferral_type=="revenue" and (source.account_type!="liability" or target.account_type!="income"): raise HTTPException(400,"გადავადებული შემოსავალი მოითხოვს liability → income ანგარიშებს")
    if payload.deferral_type=="expense" and (source.account_type!="asset" or target.account_type!="expense"): raise HTTPException(400,"გადავადებული ხარჯი მოითხოვს asset → expense ანგარიშებს")
    schedule=DeferredSchedule(company_id=current_user.company_id,created_by=current_user.id,**payload.model_dump()); db.add(schedule); await db.flush()
    monthly=money(payload.total_amount/Decimal(payload.periods)); allocated=Decimal("0")
    for index in range(payload.periods):
        amount=money(payload.total_amount-allocated) if index==payload.periods-1 else monthly; allocated+=amount
        db.add(DeferredRecognition(company_id=current_user.company_id,schedule_id=schedule.id,period_no=index+1,recognition_date=add_months(payload.start_date,index),amount=amount))
    await db.flush(); schedule=await load_schedule(db,current_user.company_id,schedule.id)
    return ResponseBase(data=await serialize(db,schedule),message="აღიარების გრაფიკი შექმნილია")

async def recognize(db:AsyncSession,user:User,item:DeferredRecognition):
    item=(await db.execute(select(DeferredRecognition).where(DeferredRecognition.id==item.id).with_for_update())).scalar_one()
    if item.status=="recognized": return item
    schedule=await load_schedule(db,user.company_id,item.schedule_id)
    accounts=(await db.execute(select(GLAccount).where(GLAccount.id.in_([schedule.source_gl_account_id,schedule.recognition_gl_account_id])))).scalars().all(); amap={a.id:a for a in accounts}
    source,target=amap[schedule.source_gl_account_id],amap[schedule.recognition_gl_account_id]; amount=money(item.amount)
    lines=[(target.code,amount,Decimal("0")),(source.code,Decimal("0"),amount)] if schedule.deferral_type=="expense" else [(source.code,amount,Decimal("0")),(target.code,Decimal("0"),amount)]
    entry=await post_journal_entry(db,user.company_id,user,entry_date=item.recognition_date,description=f"{schedule.name} — პერიოდი {item.period_no}",reference_type="deferred_recognition",reference_id=item.id,lines=lines)
    item.status="recognized"; item.journal_entry_id=entry.id; item.recognized_by=user.id; item.recognized_at=utc_now(); await db.flush()
    pending=await db.scalar(select(DeferredRecognition.id).where(DeferredRecognition.schedule_id==schedule.id,DeferredRecognition.status=="pending").limit(1))
    if not pending: schedule.status="completed"
    return item

@router.post("/recognitions/{recognition_id}/recognize",response_model=ResponseBase)
async def recognize_one(recognition_id:UUID,current_user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_role(current_user)
    item=(await db.execute(select(DeferredRecognition).where(DeferredRecognition.id==recognition_id,DeferredRecognition.company_id==current_user.company_id))).scalar_one_or_none()
    if not item: raise HTTPException(404,"აღიარების პერიოდი არ მოიძებნა")
    await recognize(db,current_user,item); return ResponseBase(message="პერიოდი აღიარებულია და GL ჩანაწერი შექმნილია")

@router.post("/recognize-due",response_model=ResponseBase[dict])
async def recognize_due(payload:RecognizeDueRequest,current_user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_role(current_user)
    rows=(await db.execute(select(DeferredRecognition).where(DeferredRecognition.company_id==current_user.company_id,DeferredRecognition.status=="pending",DeferredRecognition.recognition_date<=payload.as_of_date).order_by(DeferredRecognition.recognition_date))).scalars().all()
    for item in rows: await recognize(db,current_user,item)
    return ResponseBase(data={"recognized_count":len(rows)},message=f"აღიარებულია {len(rows)} პერიოდი")


# ── Preview (dry-run) ─────────────────────────────────────────────────────────

class PreviewDueResponse(BaseModel):
    total_pending: int
    total_amount: float
    items: list[dict]


@router.post("/preview-due", response_model=ResponseBase[PreviewDueResponse])
async def preview_due(
    payload: RecognizeDueRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Preview which periods would be recognized without executing."""
    require_role(current_user)
    rows = (await db.execute(
        select(DeferredRecognition)
        .where(
            DeferredRecognition.company_id == current_user.company_id,
            DeferredRecognition.status == "pending",
            DeferredRecognition.recognition_date <= payload.as_of_date,
        )
        .order_by(DeferredRecognition.recognition_date)
    )).scalars().all()

    items = []
    total_amount = Decimal("0")
    for r in rows:
        total_amount += r.amount
        items.append({
            "id": str(r.id),
            "schedule_id": str(r.schedule_id),
            "period_no": r.period_no,
            "recognition_date": str(r.recognition_date),
            "amount": float(r.amount),
        })

    return ResponseBase(data=PreviewDueResponse(
        total_pending=len(rows),
        total_amount=float(total_amount),
        items=items,
    ))


# ── Reversal ──────────────────────────────────────────────────────────────────

@router.post("/recognitions/{recognition_id}/reverse", response_model=ResponseBase)
async def reverse_recognition(
    recognition_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reverse a recognized period — creates reversing GL entry."""
    require_role(current_user)
    item = (await db.execute(
        select(DeferredRecognition).where(
            DeferredRecognition.id == recognition_id,
            DeferredRecognition.company_id == current_user.company_id,
        ).with_for_update()
    )).scalar_one_or_none()
    if not item:
        raise HTTPException(404, "აღიარების პერიოდი არ მოიძებნა")
    if item.status != "recognized":
        raise HTTPException(400, "მხოლოდ აღიარებული პერიოდის გაუქმება შეიძლება")

    schedule = await load_schedule(db, current_user.company_id, item.schedule_id)
    accounts = (await db.execute(
        select(GLAccount).where(GLAccount.id.in_([schedule.source_gl_account_id, schedule.recognition_gl_account_id]))
    )).scalars().all()
    amap = {a.id: a for a in accounts}
    source, target = amap[schedule.source_gl_account_id], amap[schedule.recognition_gl_account_id]
    amount = money(item.amount)

    # Reverse the lines (swap debit/credit)
    lines = [(source.code, amount, Decimal("0")), (target.code, Decimal("0"), amount)] if schedule.deferral_type == "expense" else [(target.code, amount, Decimal("0")), (source.code, Decimal("0"), amount)]

    entry = await post_journal_entry(
        db, current_user.company_id, current_user,
        entry_date=item.recognition_date,
        description=f"{schedule.name} — გაუქმება (პერიოდი {item.period_no})",
        reference_type="deferred_reversal",
        reference_id=item.id,
        lines=lines,
    )

    item.status = "pending"
    item.journal_entry_id = None
    item.recognized_by = None
    item.recognized_at = None
    schedule.status = "active"
    await db.flush()

    return ResponseBase(message="აღიარება გაუქმებულია — შექმნილია reversing GL ჩანაწერი")
