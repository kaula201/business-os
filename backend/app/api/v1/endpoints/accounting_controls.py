"""Accounting control endpoints: fiscal positions, consolidation mappings and FX rates."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.accounting_controls import ConsolidationAccountMapping, FiscalPosition, FxTranslationRate
from app.models.gl import GLAccount
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/accounting-controls", tags=["ბუღალტრული კონტროლები"])


def require_accounting_admin(user: User) -> None:
    if user.role not in (User.Role.ADMIN, User.Role.ACCOUNTANT):
        raise HTTPException(status_code=403, detail="ფინანსური კონტროლები ხელმისაწვდომია მხოლოდ ადმინის/ბუღალტრისთვის")


def _fiscal(row: FiscalPosition) -> dict:
    return {"id": str(row.id), "code": row.code, "name": row.name, "tax_type": row.tax_type,
            "vat_rate": float(row.vat_rate), "sales_tax_account_code": row.sales_tax_account_code,
            "purchase_tax_account_code": row.purchase_tax_account_code,
            "applies_to": row.applies_to, "is_default": row.is_default,
            "is_active": row.is_active}


def _mapping(row: ConsolidationAccountMapping) -> dict:
    return {"id": str(row.id), "source_account_code": row.source_account_code,
            "target_account_code": row.target_account_code, "target_name": row.target_name,
            "target_account_type": row.target_account_type, "is_active": row.is_active}


def _fx(row: FxTranslationRate) -> dict:
    return {"id": str(row.id), "target_currency": row.target_currency, "rate_date": str(row.rate_date),
            "rate": float(row.rate), "method": row.method, "source": row.source, "is_locked": row.is_locked}


@router.get("/fiscal-positions", response_model=ResponseBase[list[dict]])
async def list_fiscal_positions(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_module("accounting-controls", "can_access"))):
    require_accounting_admin(current_user)
    rows = (await db.execute(select(FiscalPosition).where(FiscalPosition.company_id == current_user.company_id).order_by(FiscalPosition.code))).scalars().all()
    return ResponseBase(data=[_fiscal(row) for row in rows])


@router.post("/fiscal-positions", response_model=ResponseBase[dict], status_code=201)
async def create_fiscal_position(data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_module("accounting-controls", "can_create"))):
    require_accounting_admin(current_user)
    if data.get("applies_to", "both") not in {"sale", "purchase", "both"}:
        raise HTTPException(status_code=422, detail="applies_to უნდა იყოს sale, purchase ან both")
    if Decimal(str(data.get("vat_rate", 18))) < 0:
        raise HTTPException(status_code=422, detail="დღგ-ის განაკვეთი უარყოფითი ვერ იქნება")
    sales_tax_account_code = data.get("sales_tax_account_code", "2200")
    purchase_tax_account_code = data.get("purchase_tax_account_code", "5300")
    accounts = (await db.execute(select(GLAccount).where(
        GLAccount.company_id == current_user.company_id,
        GLAccount.is_active.is_(True),
        GLAccount.code.in_([sales_tax_account_code, purchase_tax_account_code]),
    ))).scalars().all()
    account_map = {row.code: row for row in accounts}
    if sales_tax_account_code not in account_map or account_map[sales_tax_account_code].account_type != "liability":
        raise HTTPException(status_code=422, detail="sales tax account უნდა იყოს ამ კომპანიის liability GL account")
    if purchase_tax_account_code not in account_map or account_map[purchase_tax_account_code].account_type not in {"asset", "expense"}:
        raise HTTPException(status_code=422, detail="purchase tax account უნდა იყოს ამ კომპანიის asset/expense GL account")
    if data.get("is_default"):
        rows = (await db.execute(select(FiscalPosition).where(FiscalPosition.company_id == current_user.company_id))).scalars().all()
        for row in rows: row.is_default = False
    row = FiscalPosition(company_id=current_user.company_id, code=data.get("code", ""), name=data.get("name", ""),
                         tax_type=data.get("tax_type", "vat_standard"), vat_rate=Decimal(str(data.get("vat_rate", 18))),
                         sales_tax_account_code=sales_tax_account_code, purchase_tax_account_code=purchase_tax_account_code,
                         applies_to=data.get("applies_to", "both"), is_default=bool(data.get("is_default", False)))
    db.add(row)
    await db.flush()
    result = _fiscal(row)
    await db.commit()
    return ResponseBase(data=result, message="ფისკალური პოზიცია შეიქმნა")


@router.get("/consolidation-mappings", response_model=ResponseBase[list[dict]])
async def list_mappings(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_module("accounting-controls", "can_access"))):
    require_accounting_admin(current_user)
    rows = (await db.execute(select(ConsolidationAccountMapping).where(ConsolidationAccountMapping.company_id == current_user.company_id).order_by(ConsolidationAccountMapping.source_account_code))).scalars().all()
    return ResponseBase(data=[_mapping(row) for row in rows])


@router.post("/consolidation-mappings", response_model=ResponseBase[dict], status_code=201)
async def create_mapping(data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_module("accounting-controls", "can_create"))):
    require_accounting_admin(current_user)
    required = ("source_account_code", "target_account_code", "target_name", "target_account_type")
    if any(not data.get(k) for k in required):
        raise HTTPException(status_code=422, detail="ყველა mapping ველი სავალდებულოა")
    valid_types = {"asset", "liability", "equity", "income", "expense"}
    if data["target_account_type"] not in valid_types:
        raise HTTPException(status_code=422, detail="არასწორი target account type")
    source = (await db.execute(select(GLAccount).where(
        GLAccount.company_id == current_user.company_id,
        GLAccount.code == data["source_account_code"],
    ))).scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=422, detail="source GL account არ მოიძებნა")
    if source.account_type != data["target_account_type"]:
        raise HTTPException(status_code=422, detail="target account type source GL account-ს უნდა ემთხვეოდეს")
    row = ConsolidationAccountMapping(company_id=current_user.company_id, **{k: data[k] for k in required})
    db.add(row)
    await db.flush()
    result = _mapping(row)
    await db.commit()
    return ResponseBase(data=result, message="კონსოლიდაციის mapping შეიქმნა")


@router.get("/fx-rates", response_model=ResponseBase[list[dict]])
async def list_fx_rates(target_currency: str | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_module("accounting-controls", "can_access"))):
    require_accounting_admin(current_user)
    query = select(FxTranslationRate).where(FxTranslationRate.company_id == current_user.company_id)
    if target_currency: query = query.where(FxTranslationRate.target_currency == target_currency.upper())
    rows = (await db.execute(query.order_by(FxTranslationRate.rate_date.desc(), FxTranslationRate.method))).scalars().all()
    return ResponseBase(data=[_fx(row) for row in rows])


@router.post("/fx-rates", response_model=ResponseBase[dict], status_code=201)
async def create_fx_rate(data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_module("accounting-controls", "can_create"))):
    require_accounting_admin(current_user)
    rate = Decimal(str(data.get("rate", 0)))
    if rate <= 0: raise HTTPException(status_code=422, detail="კურსი ნულზე მეტი უნდა იყოს")
    method = data.get("method", "closing")
    if method not in {"closing", "average", "historical"}: raise HTTPException(status_code=422, detail="არასწორი translation method")
    row = FxTranslationRate(company_id=current_user.company_id, target_currency=data.get("target_currency", "GEL").upper(),
                            rate_date=date.fromisoformat(data.get("rate_date", str(date.today()))), rate=rate,
                            method=method, source=data.get("source", "manual"), is_locked=bool(data.get("is_locked", False)))
    db.add(row)
    await db.flush()
    result = _fx(row)
    await db.commit()
    return ResponseBase(data=result, message="FX translation კურსი შეიქმნა")
