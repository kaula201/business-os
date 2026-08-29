"""Consolidated (multi-company) accounting API endpoints."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.purchase_orders import add_audit
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import ResponseBase
from app.services.consolidated import (
    consolidated_balance_sheet,
    consolidated_profit_loss,
    get_group_companies,
    intercompany_balances,
)

router = APIRouter(prefix="/gl/consolidated", tags=["მთავარი წიგნი — კონსოლიდირებული"])


def require_gl_role(user: User) -> None:
    if user.role not in (User.Role.ADMIN, User.Role.ACCOUNTANT):
        raise HTTPException(status_code=403, detail="მთავარი წიგნის ოპერაციები ხელმისაწვდომია მხოლოდ ადმინის/ბუღალტერისთვის")


async def _group_ids(db: AsyncSession, current_user: User) -> tuple[list, list]:
    companies = await get_group_companies(db, current_user.company_id)
    return [c.id for c in companies], companies


@router.get("/companies")
async def consolidated_companies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Companies included in the current user's consolidated scope."""
    require_gl_role(current_user)
    _, companies = await _group_ids(db, current_user)
    return ResponseBase(data=[
        {"id": str(c.id), "name": c.name, "identification_code": c.identification_code}
        for c in companies
    ])


@router.get("/profit-loss")
async def consolidated_pl(
    date_from: date | None = None,
    date_to: date | None = None,
    presentation_currency: str | None = Query(None, min_length=3, max_length=3),
    fx_method: str = Query("average", pattern="^(average|closing|historical)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_gl_role(current_user)
    company_ids, companies = await _group_ids(db, current_user)
    today = date.today()
    from_date = date_from or date(today.year, today.month, 1)
    to_date = date_to or today
    try:
        data = await consolidated_profit_loss(db, company_ids, from_date, to_date, presentation_currency, fx_method)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    data["companies"] = [{"id": str(c.id), "name": c.name} for c in companies]
    add_audit(db, current_user, "consolidated.pl_viewed", "gl", company_ids[0], {
        "company_ids": [str(c) for c in company_ids],
        "date_from": str(from_date), "date_to": str(to_date),
    })
    await db.commit()
    return ResponseBase(data=data)


@router.get("/balance-sheet")
async def consolidated_bs(
    as_of_date: date | None = None,
    presentation_currency: str | None = Query(None, min_length=3, max_length=3),
    fx_method: str = Query("closing", pattern="^(average|closing|historical)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_gl_role(current_user)
    company_ids, companies = await _group_ids(db, current_user)
    target_date = as_of_date or date.today()
    try:
        data = await consolidated_balance_sheet(db, company_ids, target_date, presentation_currency, fx_method)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    data["companies"] = [{"id": str(c.id), "name": c.name} for c in companies]
    add_audit(db, current_user, "consolidated.bs_viewed", "gl", company_ids[0], {
        "company_ids": [str(c) for c in company_ids],
        "as_of_date": str(target_date),
    })
    await db.commit()
    return ResponseBase(data=data)


@router.get("/intercompany-balances")
async def consolidated_intercompany(
    as_of_date: date | None = None,
    presentation_currency: str | None = Query(None, min_length=3, max_length=3),
    fx_method: str = Query("closing", pattern="^(average|closing|historical)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-account balances across group companies — intercompany reconciliation."""
    require_gl_role(current_user)
    company_ids, companies = await _group_ids(db, current_user)
    target_date = as_of_date or date.today()
    try:
        data = await intercompany_balances(db, company_ids, target_date, presentation_currency, fx_method)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    data["companies"] = [{"id": str(c.id), "name": c.name} for c in companies]
    add_audit(db, current_user, "consolidated.intercompany_viewed", "gl", company_ids[0], {
        "company_ids": [str(c) for c in company_ids],
        "as_of_date": str(target_date),
    })
    await db.commit()
    return ResponseBase(data=data)


@router.get("/checks", response_model=ResponseBase[dict])
async def consolidated_checks(
    as_of_date: date = Query(default_factory=date.today),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Consolidation health checks (Odoo-depth):
    1. Each company's balance sheet is balanced (assets == liabilities + equity)
    2. Intercompany balances match across companies (A's receivable == B's payable)
    3. Elimination entries exist for matched intercompany pairs
    """
    require_gl_role(current_user)
    company_ids, companies = await _group_ids(db, current_user)

    checks = []
    # 1. per-company BS balance
    for c in companies:
        bs = await consolidated_balance_sheet(db, [c.id], as_of_date)
        assets = float(bs.get("total_assets", 0) or 0)
        liabilities = float(bs.get("total_liabilities", 0) or 0)
        equity = float(bs.get("total_equity", 0) or 0)
        checks.append({
            "company_id": str(c.id), "company_name": c.name,
            "check": "balance_sheet_balanced",
            "ok": abs(assets - (liabilities + equity)) < 0.01,
            "assets": round(assets, 2), "liabilities": round(liabilities, 2),
            "equity": round(equity, 2),
            "difference": round(assets - (liabilities + equity), 2),
        })

    # 2. intercompany match
    ic = await intercompany_balances(db, company_ids, as_of_date)
    for acc in ic.get("accounts", []):
        balances = [float(b["balance"]) for b in acc.get("balances", {}).values() if b is not None]
        total = sum(balances)
        checks.append({
            "account_code": acc.get("account_code"), "account_name": acc.get("account_name"),
            "check": "intercompany_matches",
            "ok": abs(total) < 0.01,
            "total": round(total, 2),
        })

    # 3. eliminations present
    from app.models.consolidation_elimination import ConsolidationElimination
    elim_count = (await db.execute(
        select(func.count()).select_from(ConsolidationElimination).where(
            ConsolidationElimination.company_id.in_(company_ids),
        )
    )).scalar()
    checks.append({
        "check": "eliminations_recorded",
        "ok": (elim_count or 0) > 0,
        "elimination_count": elim_count or 0,
    })

    add_audit(db, current_user, "consolidated.checks_viewed", "gl", company_ids[0], {
        "as_of_date": as_of_date.isoformat(), "checks": len(checks),
    })
    await db.commit()

    return ResponseBase(data={
        "as_of_date": as_of_date.isoformat(),
        "checks": checks,
        "all_ok": all(c["ok"] for c in checks),
    })
