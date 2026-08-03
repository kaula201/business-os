"""Cash register API: cash accounts and transactions."""
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.audit import AuditLog
from app.models.cash import CashAccount, CashTransaction
from app.models.user import User
from app.schemas.cash import (
    CashAccountCreate,
    CashAccountResponse,
    CashAccountUpdate,
    CashDailyReport,
    CashTransactionCreate,
    CashTransactionResponse,
)
from app.schemas.common import ResponseBase
from app.services.accounting_periods import ensure_period_open

router = APIRouter(prefix="/cash", tags=["სალარო"])


# ── Helpers ──────────────────────────────────────────────────────────

def add_cash_audit(
    db: AsyncSession,
    current_user: User,
    action: str,
    entity_type: str,
    entity_id: UUID,
    details: dict,
) -> None:
    db.add(
        AuditLog(
            company_id=current_user.company_id,
            user_id=current_user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=json.dumps(details, ensure_ascii=False, default=str),
        )
    )


async def get_company_cash_account(
    db: AsyncSession, account_id: UUID, company_id: UUID
) -> CashAccount:
    account = (
        await db.execute(
            select(CashAccount).where(
                CashAccount.id == account_id,
                CashAccount.company_id == company_id,
            )
        )
    ).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="სალარო არ მოიძებნა")
    return account


# ── Cash Accounts ──────────────────────────────────────────────────

@router.get("/accounts", response_model=ResponseBase[list[CashAccountResponse]])
async def list_cash_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CashAccount)
        .where(CashAccount.company_id == current_user.company_id)
        .order_by(CashAccount.name)
    )
    accounts = result.scalars().all()
    return ResponseBase(data=accounts)


@router.post("/accounts", response_model=ResponseBase[CashAccountResponse], status_code=201)
async def create_cash_account(
    payload: CashAccountCreate,
    current_user: User = Depends(require_module("cash", "can_create")),
    db: AsyncSession = Depends(get_db),
):
    account = CashAccount(
        company_id=current_user.company_id,
        **payload.model_dump(),
    )
    db.add(account)
    await db.flush()
    add_cash_audit(
        db, current_user, "create", "cash_account", account.id,
        {"name": account.name, "currency": account.currency},
    )
    await db.refresh(account)
    return ResponseBase(data=account, message="სალარო დამატებულია")


@router.put("/accounts/{account_id}", response_model=ResponseBase[CashAccountResponse])
async def update_cash_account(
    account_id: UUID,
    payload: CashAccountUpdate,
    current_user: User = Depends(require_module("cash", "can_edit")),
    db: AsyncSession = Depends(get_db),
):
    account = await get_company_cash_account(db, account_id, current_user.company_id)
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="განახლების მონაცემები არ არის მოწოდებული")
    for key, value in update_data.items():
        setattr(account, key, value)
    await db.flush()
    add_cash_audit(
        db, current_user, "update", "cash_account", account.id,
        {"updated_fields": list(update_data.keys())},
    )
    await db.refresh(account)
    return ResponseBase(data=account, message="სალარო განახლებულია")


@router.delete("/accounts/{account_id}", response_model=ResponseBase)
async def delete_cash_account(
    account_id: UUID,
    current_user: User = Depends(require_module("cash", "can_edit")),
    db: AsyncSession = Depends(get_db),
):
    account = await get_company_cash_account(db, account_id, current_user.company_id)
    has_transactions = await db.scalar(
        select(CashTransaction.id).where(
            CashTransaction.cash_account_id == account_id,
            CashTransaction.company_id == current_user.company_id,
        ).limit(1)
    )
    if has_transactions:
        raise HTTPException(
            status_code=409,
            detail="ოპერაციების ისტორიის მქონე სალაროს წაშლა არ შეიძლება; შეგიძლიათ გამორთოთ",
        )
    await db.delete(account)
    add_cash_audit(
        db, current_user, "delete", "cash_account", account_id,
        {"name": account.name},
    )
    return ResponseBase(message="სალარო წაშლილია")


# ── Cash Transactions ───────────────────────────────────────────────

@router.get("/accounts/{account_id}/transactions", response_model=ResponseBase[list[CashTransactionResponse]])
async def list_cash_transactions(
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_company_cash_account(db, account_id, current_user.company_id)
    result = await db.execute(
        select(CashTransaction)
        .where(
            CashTransaction.cash_account_id == account_id,
            CashTransaction.company_id == current_user.company_id,
        )
        .order_by(CashTransaction.transaction_date.desc(), CashTransaction.created_at.desc())
    )
    transactions = result.scalars().all()
    return ResponseBase(data=transactions)


@router.post("/accounts/{account_id}/transactions", response_model=ResponseBase[CashTransactionResponse], status_code=201)
async def create_cash_transaction(
    account_id: UUID,
    payload: CashTransactionCreate,
    current_user: User = Depends(require_module("cash", "can_create")),
    db: AsyncSession = Depends(get_db),
):
    await ensure_period_open(db, current_user.company_id, payload.transaction_date)
    account = await get_company_cash_account(db, account_id, current_user.company_id)

    # Update balance
    if payload.direction == "inflow":
        account.balance += payload.amount
    else:
        if account.balance < payload.amount:
            raise HTTPException(status_code=400, detail="სალაროში საკმარისი თანხა არ არის")
        account.balance -= payload.amount

    transaction = CashTransaction(
        company_id=current_user.company_id,
        cash_account_id=account_id,
        created_by=current_user.id,
        **payload.model_dump(exclude={"cash_account_id"}),
    )
    db.add(transaction)
    await db.flush()
    transaction.cash_account_name = account.name
    add_cash_audit(
        db, current_user, "create", "cash_transaction", transaction.id,
        {"account": account.name, "direction": payload.direction, "amount": str(payload.amount), "category": payload.category},
    )
    await db.refresh(transaction)
    return ResponseBase(data=transaction, message="ოპერაცია დაფიქსირებულია")


@router.get("/accounts/{account_id}/daily-report", response_model=ResponseBase[CashDailyReport])
async def cash_daily_report(
    account_id: UUID,
    report_date: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get daily cash report: opening balance, inflow, outflow, closing balance."""
    from datetime import date as date_type
    target_date = date_type.fromisoformat(report_date) if report_date else date_type.today()

    account = await get_company_cash_account(db, account_id, current_user.company_id)

    # Get all transactions before today to calculate opening balance
    prior_result = await db.execute(
        select(sa_func.coalesce(sa_func.sum(CashTransaction.amount), 0))
        .where(
            CashTransaction.cash_account_id == account_id,
            CashTransaction.company_id == current_user.company_id,
            CashTransaction.transaction_date < target_date,
            CashTransaction.direction == "inflow",
        )
    )
    prior_inflow = prior_result.scalar()

    prior_out_result = await db.execute(
        select(sa_func.coalesce(sa_func.sum(CashTransaction.amount), 0))
        .where(
            CashTransaction.cash_account_id == account_id,
            CashTransaction.company_id == current_user.company_id,
            CashTransaction.transaction_date < target_date,
            CashTransaction.direction == "outflow",
        )
    )
    prior_outflow = prior_out_result.scalar()
    opening_balance = float(prior_inflow - prior_outflow)

    # Today's transactions
    today_in_result = await db.execute(
        select(sa_func.coalesce(sa_func.sum(CashTransaction.amount), 0))
        .where(
            CashTransaction.cash_account_id == account_id,
            CashTransaction.company_id == current_user.company_id,
            CashTransaction.transaction_date == target_date,
            CashTransaction.direction == "inflow",
        )
    )
    today_inflow = float(today_in_result.scalar())

    today_out_result = await db.execute(
        select(sa_func.coalesce(sa_func.sum(CashTransaction.amount), 0))
        .where(
            CashTransaction.cash_account_id == account_id,
            CashTransaction.company_id == current_user.company_id,
            CashTransaction.transaction_date == target_date,
            CashTransaction.direction == "outflow",
        )
    )
    today_outflow = float(today_out_result.scalar())

    count_result = await db.execute(
        select(sa_func.count())
        .select_from(CashTransaction)
        .where(
            CashTransaction.cash_account_id == account_id,
            CashTransaction.company_id == current_user.company_id,
            CashTransaction.transaction_date == target_date,
        )
    )
    tx_count = count_result.scalar()

    report = CashDailyReport(
        date=target_date,
        opening_balance=opening_balance,
        total_inflow=today_inflow,
        total_outflow=today_outflow,
        closing_balance=opening_balance + today_inflow - today_outflow,
        transaction_count=tx_count,
    )
    return ResponseBase(data=report)
