"""Batch-approve bank reconciliation suggestions (debit→payable, credit→receivable).

This module is a leaf: it imports both the supplier (banking) and customer
reconcile flows and reuses their single-row create endpoints, so every item is
idempotency-safe and posts the exact same GL entries as a manual reconcile.
No module that lives lower in the import graph imports this one, so there is
no circular import.
"""
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.banking import BankReconciliationCreate
from app.schemas.common import ResponseBase
from app.schemas.receivable import CustomerBankReconciliationCreate

from app.api.v1.endpoints.banking import reconcile_bank_transaction
from app.api.v1.endpoints.customer_finance import reconcile_customer_receivable

router = APIRouter(tags=["საბანკო ოპერაციები — ჯგუფური შეჯერება"])


class BatchApproveItem(BaseModel):
    transaction_id: UUID
    kind: Literal["payable", "receivable"]
    candidate_id: UUID
    amount: float = Field(gt=0)
    notes: str | None = None


class BatchApproveRequest(BaseModel):
    items: list[BatchApproveItem] = Field(min_length=1, max_length=50)


@router.post("/bank-reconciliations/batch-approve", response_model=ResponseBase[dict])
async def batch_approve_suggestions(
    data: BatchApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve several reconciliation suggestions in one call.

    Each item delegates to the corresponding single-row reconcile endpoint, so
    the exact same validation, idempotency and GL posting logic is applied.
    A failure on one item raises and rolls back the whole batch; re-submitting
    an already-applied item is idempotently returned.
    """
    if current_user.role not in {User.Role.ADMIN, User.Role.ACCOUNTANT}:
        raise HTTPException(status_code=403, detail="საბანკო ოპერაციის შესრულების უფლება არ გაქვთ")

    results = []
    for item in data.items:
        if item.kind == "payable":
            resp = await reconcile_bank_transaction(
                transaction_id=item.transaction_id,
                data=BankReconciliationCreate(
                    idempotency_key=f"batch:{item.transaction_id}:{item.candidate_id}",
                    supplier_payable_id=item.candidate_id,
                    amount=Decimal(str(item.amount)),
                    notes=item.notes,
                ),
                db=db,
                current_user=current_user,
            )
            rec_id = resp.data.reconciliation.id if resp.data else None
            results.append({"transaction_id": str(item.transaction_id), "kind": "payable",
                            "reconciliation_id": str(rec_id) if rec_id else None, "status": "reconciled"})
        else:
            resp = await reconcile_customer_receivable(
                transaction_id=item.transaction_id,
                data=CustomerBankReconciliationCreate(
                    idempotency_key=f"batch:{item.transaction_id}:{item.candidate_id}",
                    customer_receivable_id=item.candidate_id,
                    amount=item.amount,
                    notes=item.notes,
                ),
                db=db,
                current_user=current_user,
            )
            rec_id = resp.data.reconciliation.id if resp.data else None
            results.append({"transaction_id": str(item.transaction_id), "kind": "receivable",
                            "reconciliation_id": str(rec_id) if rec_id else None, "status": "reconciled"})

    return ResponseBase(data={"processed": len(results), "results": results}, message="ჯგუფური შეჯერება დასრულდა")
