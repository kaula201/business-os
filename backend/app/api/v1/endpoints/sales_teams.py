"""Sales teams, targets, commissions API."""
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.purchase_orders import add_audit
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.hr import Payslip
from app.models.sales_team import (
    CommissionAccrual,
    CommissionRule,
    SalesTarget,
    SalesTeam,
    SalesTeamMember,
)
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.sales_team import (
    CommissionAccrualResponse,
    CommissionAdjustRequest,
    CommissionApproveRequest,
    CommissionPayrollLinkRequest,
    CommissionRuleCreate,
    CommissionRuleResponse,
    CommissionRuleUpdate,
    SalesTargetCreate,
    SalesTargetResponse,
    SalesTargetUpdate,
    SalesTeamCreate,
    SalesTeamMemberCreate,
    SalesTeamMemberResponse,
    SalesTeamResponse,
    SalesTeamUpdate,
)

router = APIRouter(prefix="/sales", tags=["გაყიდვების გუნდები"])


def _team_response(t: SalesTeam, member_count: int = 0) -> SalesTeamResponse:
    return SalesTeamResponse(
        id=t.id, company_id=t.company_id, name=t.name, manager_id=t.manager_id,
        description=t.description, is_active=t.is_active, member_count=member_count,
        created_at=t.created_at, updated_at=t.updated_at,
    )


# ── Sales teams ──────────────────────────────────────────────────────────────


@router.get("/teams/", response_model=ResponseBase[PaginatedResponse[SalesTeamResponse]])
async def list_teams(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [SalesTeam.company_id == current_user.company_id]
    if is_active is not None:
        filters.append(SalesTeam.is_active == is_active)
    total = (await db.execute(select(func.count(SalesTeam.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(
            select(SalesTeam).options(selectinload(SalesTeam.members))
            .where(*filters).order_by(SalesTeam.name.asc())
            .offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[_team_response(r, len(r.members)) for r in rows],
    ))


@router.post("/teams/", response_model=ResponseBase[SalesTeamResponse], status_code=201)
async def create_team(
    data: SalesTeamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    team = SalesTeam(
        company_id=current_user.company_id, name=data.name,
        manager_id=data.manager_id, description=data.description,
    )
    db.add(team)
    await db.flush()
    add_audit(db, current_user, "sales_team.created", "sales_team", team.id, {"name": team.name})
    await db.commit()
    await db.refresh(team)
    return ResponseBase(data=_team_response(team))


@router.patch("/teams/{team_id}", response_model=ResponseBase[SalesTeamResponse])
async def update_team(
    team_id: uuid.UUID,
    data: SalesTeamUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    team = (await db.execute(select(SalesTeam).where(
        SalesTeam.id == team_id, SalesTeam.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="გუნდი ვერ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(team, field, value)
    add_audit(db, current_user, "sales_team.updated", "sales_team", team.id, {})
    await db.commit()
    await db.refresh(team)
    return ResponseBase(data=_team_response(team))


@router.delete("/teams/{team_id}", response_model=ResponseBase)
async def delete_team(
    team_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    team = (await db.execute(select(SalesTeam).where(
        SalesTeam.id == team_id, SalesTeam.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="გუნდი ვერ მოიძებნა")
    await db.delete(team)
    add_audit(db, current_user, "sales_team.deleted", "sales_team", team.id, {})
    await db.commit()
    return ResponseBase(message="გუნდი წაშლილია")


# ── Team members ─────────────────────────────────────────────────────────────


@router.post("/teams/{team_id}/members", response_model=ResponseBase[SalesTeamMemberResponse], status_code=201)
async def add_member(
    team_id: uuid.UUID,
    data: SalesTeamMemberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    team = (await db.execute(select(SalesTeam).where(
        SalesTeam.id == team_id, SalesTeam.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="გუნდი ვერ მოიძებნა")
    member = SalesTeamMember(team_id=team_id, user_id=data.user_id)
    db.add(member)
    await db.flush()
    add_audit(db, current_user, "sales_team.member_added", "sales_team", team.id, {"user_id": str(data.user_id)})
    await db.commit()
    return ResponseBase(data=SalesTeamMemberResponse(id=member.id, team_id=member.team_id, user_id=member.user_id))


@router.delete("/teams/{team_id}/members/{user_id}", response_model=ResponseBase)
async def remove_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = (await db.execute(select(SalesTeamMember).where(
        SalesTeamMember.team_id == team_id,
        SalesTeamMember.user_id == user_id,
        SalesTeamMember.team.has(SalesTeam.company_id == current_user.company_id),
    ))).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="წევრი ვერ მოიძებნა")
    await db.delete(member)
    add_audit(db, current_user, "sales_team.member_removed", "sales_team", team_id, {"user_id": str(user_id)})
    await db.commit()
    return ResponseBase(message="წევრი ამოღებულია")


# ── Sales targets ────────────────────────────────────────────────────────────


@router.get("/targets/", response_model=ResponseBase[PaginatedResponse[SalesTargetResponse]])
async def list_targets(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    period: str | None = None,
    team_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [SalesTarget.company_id == current_user.company_id]
    if period:
        filters.append(SalesTarget.period == period)
    if team_id:
        filters.append(SalesTarget.team_id == team_id)
    total = (await db.execute(select(func.count(SalesTarget.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(select(SalesTarget).where(*filters).order_by(SalesTarget.period.desc())
                         .offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    items = []
    for r in rows:
        progress = (Decimal(str(r.achieved_amount)) / Decimal(str(r.target_amount)) * 100) if r.target_amount > 0 else 0
        items.append(SalesTargetResponse(
            id=r.id, company_id=r.company_id, period=r.period, team_id=r.team_id,
            owner_id=r.owner_id, target_amount=float(r.target_amount),
            achieved_amount=float(r.achieved_amount), progress_percent=float(progress),
            created_at=r.created_at, updated_at=r.updated_at,
        ))
    return ResponseBase(data=PaginatedResponse(total=total, page=page, page_size=page_size, items=items))


@router.post("/targets/", response_model=ResponseBase[SalesTargetResponse], status_code=201)
async def create_target(
    data: SalesTargetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = SalesTarget(
        company_id=current_user.company_id, period=data.period, team_id=data.team_id,
        owner_id=data.owner_id, target_amount=data.target_amount,
    )
    db.add(target)
    await db.flush()
    add_audit(db, current_user, "sales_target.created", "sales_target", target.id,
              {"period": data.period, "target": str(data.target_amount)})
    await db.commit()
    await db.refresh(target)
    return ResponseBase(data=SalesTargetResponse(
        id=target.id, company_id=target.company_id, period=target.period,
        team_id=target.team_id, owner_id=target.owner_id,
        target_amount=float(target.target_amount), achieved_amount=float(target.achieved_amount),
        progress_percent=0, created_at=target.created_at, updated_at=target.updated_at,
    ))


@router.patch("/targets/{target_id}", response_model=ResponseBase[SalesTargetResponse])
async def update_target(
    target_id: uuid.UUID,
    data: SalesTargetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = (await db.execute(select(SalesTarget).where(
        SalesTarget.id == target_id, SalesTarget.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="მიზანი ვერ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(target, field, value)
    await db.commit()
    await db.refresh(target)
    progress = (Decimal(str(target.achieved_amount)) / Decimal(str(target.target_amount)) * 100) if target.target_amount > 0 else 0
    return ResponseBase(data=SalesTargetResponse(
        id=target.id, company_id=target.company_id, period=target.period,
        team_id=target.team_id, owner_id=target.owner_id,
        target_amount=float(target.target_amount), achieved_amount=float(target.achieved_amount),
        progress_percent=float(progress), created_at=target.created_at, updated_at=target.updated_at,
    ))


@router.delete("/targets/{target_id}", response_model=ResponseBase)
async def delete_target(
    target_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = (await db.execute(select(SalesTarget).where(
        SalesTarget.id == target_id, SalesTarget.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="მიზანი ვერ მოიძებნა")
    await db.delete(target)
    await db.commit()
    return ResponseBase(message="მიზანი წაშლილია")


# ── Commission rules ─────────────────────────────────────────────────────────


@router.get("/commission-rules/", response_model=ResponseBase[PaginatedResponse[CommissionRuleResponse]])
async def list_commission_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [CommissionRule.company_id == current_user.company_id]
    if is_active is not None:
        filters.append(CommissionRule.is_active == is_active)
    total = (await db.execute(select(func.count(CommissionRule.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(select(CommissionRule).where(*filters).order_by(CommissionRule.name.asc())
                         .offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[CommissionRuleResponse(
            id=r.id, company_id=r.company_id, name=r.name, team_id=r.team_id,
            owner_id=r.owner_id, product_category_id=r.product_category_id,
            rate_percent=float(r.rate_percent), fixed_amount=float(r.fixed_amount),
            is_active=r.is_active, created_at=r.created_at, updated_at=r.updated_at,
        ) for r in rows],
    ))


@router.post("/commission-rules/", response_model=ResponseBase[CommissionRuleResponse], status_code=201)
async def create_commission_rule(
    data: CommissionRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.rate_percent == 0 and data.fixed_amount == 0:
        raise HTTPException(status_code=400, detail="rate_percent ან fixed_amount უნდა იყოს ნულისგან განსხვავებული")
    rule = CommissionRule(
        company_id=current_user.company_id, name=data.name, team_id=data.team_id,
        owner_id=data.owner_id, product_category_id=data.product_category_id,
        rate_percent=data.rate_percent, fixed_amount=data.fixed_amount,
    )
    db.add(rule)
    await db.flush()
    add_audit(db, current_user, "commission_rule.created", "commission_rule", rule.id, {"name": rule.name})
    await db.commit()
    await db.refresh(rule)
    return ResponseBase(data=CommissionRuleResponse(
        id=rule.id, company_id=rule.company_id, name=rule.name, team_id=rule.team_id,
        owner_id=rule.owner_id, product_category_id=rule.product_category_id,
        rate_percent=float(rule.rate_percent), fixed_amount=float(rule.fixed_amount),
        is_active=rule.is_active, created_at=rule.created_at, updated_at=rule.updated_at,
    ))


@router.patch("/commission-rules/{rule_id}", response_model=ResponseBase[CommissionRuleResponse])
async def update_commission_rule(
    rule_id: uuid.UUID,
    data: CommissionRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = (await db.execute(select(CommissionRule).where(
        CommissionRule.id == rule_id, CommissionRule.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="საკომისიო წესი ვერ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    add_audit(db, current_user, "commission_rule.updated", "commission_rule", rule.id, {})
    await db.commit()
    await db.refresh(rule)
    return ResponseBase(data=CommissionRuleResponse(
        id=rule.id, company_id=rule.company_id, name=rule.name, team_id=rule.team_id,
        owner_id=rule.owner_id, product_category_id=rule.product_category_id,
        rate_percent=float(rule.rate_percent), fixed_amount=float(rule.fixed_amount),
        is_active=rule.is_active, created_at=rule.created_at, updated_at=rule.updated_at,
    ))


@router.delete("/commission-rules/{rule_id}", response_model=ResponseBase)
async def delete_commission_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = (await db.execute(select(CommissionRule).where(
        CommissionRule.id == rule_id, CommissionRule.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="საკომისიო წესი ვერ მოიძებნა")
    await db.delete(rule)
    await db.commit()
    return ResponseBase(message="საკომისიო წესი წაშლილია")


# ── Commission accruals ──────────────────────────────────────────────────────


@router.get("/commissions/", response_model=ResponseBase[PaginatedResponse[CommissionAccrualResponse]])
async def list_commissions(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    status: str | None = None,
    owner_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [CommissionAccrual.company_id == current_user.company_id]
    if status:
        filters.append(CommissionAccrual.status == status)
    if owner_id:
        filters.append(CommissionAccrual.owner_id == owner_id)
    total = (await db.execute(select(func.count(CommissionAccrual.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(select(CommissionAccrual).where(*filters).order_by(CommissionAccrual.created_at.desc())
                         .offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[CommissionAccrualResponse(
            id=r.id, company_id=r.company_id, rule_id=r.rule_id, order_id=r.order_id,
            owner_id=r.owner_id, team_id=r.team_id, base_amount=float(r.base_amount),
            commission_amount=float(r.commission_amount), status=r.status,
            paid_at=r.paid_at, created_at=r.created_at,
        ) for r in rows],
    ))


@router.post("/commissions/{accrual_id}/mark-paid", response_model=ResponseBase[CommissionAccrualResponse])
async def mark_commission_paid(
    accrual_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    accrual = (await db.execute(select(CommissionAccrual).where(
        CommissionAccrual.id == accrual_id,
        CommissionAccrual.company_id == current_user.company_id,
    ).with_for_update())).scalar_one_or_none()
    if not accrual:
        raise HTTPException(status_code=404, detail="დარიცხვა ვერ მოიძებნა")
    from app.core.time import utc_now
    accrual.status = "paid"
    accrual.paid_at = utc_now()
    add_audit(db, current_user, "commission.paid", "commission_accrual", accrual.id, {})
    await db.commit()
    await db.refresh(accrual)
    return ResponseBase(data=CommissionAccrualResponse(
        id=accrual.id, company_id=accrual.company_id, rule_id=accrual.rule_id,
        order_id=accrual.order_id, owner_id=accrual.owner_id, team_id=accrual.team_id,
        base_amount=float(accrual.base_amount), commission_amount=float(accrual.commission_amount),
        status=accrual.status, paid_at=accrual.paid_at, created_at=accrual.created_at,
        approved_at=accrual.approved_at, approved_by=accrual.approved_by,
        payslip_id=accrual.payslip_id, return_id=accrual.return_id,
        adjustment_of=accrual.adjustment_of, adjustment_reason=accrual.adjustment_reason,
    ))


# ── Sales Teams 2.0 — approval / return adjustment / payroll link ─────────────

def _accrual_response(a: CommissionAccrual) -> CommissionAccrualResponse:
    return CommissionAccrualResponse(
        id=a.id, company_id=a.company_id, rule_id=a.rule_id, order_id=a.order_id,
        owner_id=a.owner_id, team_id=a.team_id, base_amount=float(a.base_amount),
        commission_amount=float(a.commission_amount), status=a.status,
        paid_at=a.paid_at, created_at=a.created_at,
        approved_at=a.approved_at, approved_by=a.approved_by,
        payslip_id=a.payslip_id, return_id=a.return_id,
        adjustment_of=a.adjustment_of, adjustment_reason=a.adjustment_reason,
    )


@router.post("/commissions/{accrual_id}/approve", response_model=ResponseBase[CommissionAccrualResponse])
async def approve_commission(
    accrual_id: uuid.UUID,
    data: CommissionApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """საკომისიოს დადასტურება (approve) ან უარყოფა (reject)."""
    accrual = (await db.execute(select(CommissionAccrual).where(
        CommissionAccrual.id == accrual_id,
        CommissionAccrual.company_id == current_user.company_id,
    ).with_for_update())).scalar_one_or_none()
    if not accrual:
        raise HTTPException(status_code=404, detail="დარიცხვა ვერ მოიძებნა")
    if accrual.status not in ("accrued", "adjusted"):
        raise HTTPException(status_code=400, detail=f"სტატუსი {accrual.status} — დადასტურება შეუძლებელია")
    from app.core.time import utc_now
    if data.approve:
        accrual.status = "approved"
        accrual.approved_at = utc_now()
        accrual.approved_by = current_user.id
        add_audit(db, current_user, "commission.approved", "commission_accrual", accrual.id,
                  {"reason": data.reason})
    else:
        accrual.status = "cancelled"
        add_audit(db, current_user, "commission.rejected", "commission_accrual", accrual.id,
                  {"reason": data.reason})
    await db.commit()
    await db.refresh(accrual)
    return ResponseBase(data=_accrual_response(accrual))


@router.post("/commissions/{accrual_id}/adjust", response_model=ResponseBase[CommissionAccrualResponse])
async def adjust_commission(
    accrual_id: uuid.UUID,
    data: CommissionAdjustRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """დაბრუნებისას საკომისიოს კორექტირება: ძველი დარიცხვა იხურება, ახალი იქმნება."""
    accrual = (await db.execute(select(CommissionAccrual).where(
        CommissionAccrual.id == accrual_id,
        CommissionAccrual.company_id == current_user.company_id,
    ).with_for_update())).scalar_one_or_none()
    if not accrual:
        raise HTTPException(status_code=404, detail="დარიცხვა ვერ მოიძებნა")
    if accrual.status == "paid":
        raise HTTPException(status_code=400, detail="გადახდილი საკომისიოს კორექტირება შეუძლებელია — ჯერ payroll-ში უკუგება გააკეთეთ")

    from app.core.time import utc_now
    # close the original
    accrual.status = "cancelled"
    accrual.adjustment_reason = data.reason
    # new adjusted accrual (negative commission = clawback)
    new_amount = data.amount if data.amount is not None else -accrual.commission_amount
    new_accrual = CommissionAccrual(
        company_id=accrual.company_id, rule_id=accrual.rule_id, order_id=accrual.order_id,
        owner_id=accrual.owner_id, team_id=accrual.team_id,
        base_amount=accrual.base_amount, commission_amount=new_amount,
        status="adjusted", adjustment_of=accrual.id, adjustment_reason=data.reason,
        return_id=accrual.return_id,
    )
    db.add(new_accrual)
    await db.flush()
    add_audit(db, current_user, "commission.adjusted", "commission_accrual", new_accrual.id,
              {"original": str(accrual.id), "reason": data.reason, "amount": str(new_amount)})
    await db.commit()
    await db.refresh(new_accrual)
    return ResponseBase(data=_accrual_response(new_accrual))


@router.post("/commissions/{accrual_id}/link-payslip", response_model=ResponseBase[CommissionAccrualResponse])
async def link_commission_to_payslip(
    accrual_id: uuid.UUID,
    data: CommissionPayrollLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """სახელფასო მოდულთან კავშირი: დარიცხვა ებმება payslip-ს."""
    accrual = (await db.execute(select(CommissionAccrual).where(
        CommissionAccrual.id == accrual_id,
        CommissionAccrual.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not accrual:
        raise HTTPException(status_code=404, detail="დარიცხვა ვერ მოიძებნა")
    payslip = (await db.execute(select(Payslip).where(
        Payslip.id == data.payslip_id, Payslip.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not payslip:
        raise HTTPException(status_code=404, detail="Payslip ვერ მოიძებნა")
    accrual.payslip_id = data.payslip_id
    if accrual.status == "approved":
        accrual.status = "paid"
        from app.core.time import utc_now
        accrual.paid_at = utc_now()
    add_audit(db, current_user, "commission.linked_payslip", "commission_accrual", accrual.id,
              {"payslip_id": str(data.payslip_id)})
    await db.commit()
    await db.refresh(accrual)
    return ResponseBase(data=_accrual_response(accrual))
