"""Bank reconciliation rules service — applies rules to unmatched bank transactions.

Actions:
  - auto_reconcile: match an open supplier payable + payment by amount/date and
    reconcile the bank transaction against it (reuses banking.reconcile flow).
  - categorize: post a GL journal entry (fee/interest/other) to gl_account_id.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bank_rule import BankReconciliationRule
from app.models.banking import BankTransaction


def _rule_matches(rule: BankReconciliationRule, txn: BankTransaction) -> bool:
    """Check whether a single rule matches a transaction.

    Note: BankTransaction.direction uses debit/credit; rules use in/out.
    """
    # direction guard (debit = out, credit = in)
    if rule.direction == "in" and txn.direction != "credit":
        return False
    if rule.direction == "out" and txn.direction != "debit":
        return False

    rt = rule.rule_type
    if rt == "description_contains":
        return bool(rule.match_text and rule.match_text.lower() in txn.description.lower())
    if rt == "counterparty_equals":
        return bool(rule.match_text and rule.match_text.lower() == txn.counterparty.lower())
    if rt == "reference_equals":
        return bool(rule.match_text and rule.match_text.lower() == txn.reference.lower())
    if rt == "amount_date":
        if rule.match_amount is None:
            return False
        # amount sign: incoming (credit) transactions positive, outgoing (debit) negative
        amount = txn.amount if txn.direction == "credit" else -txn.amount
        return abs(amount - rule.match_amount) < Decimal("0.005")
    return False


async def apply_rules(
    db: AsyncSession,
    company_id: uuid.UUID,
    on_date: date | None = None,
    user_id: uuid.UUID | None = None,
) -> dict:
    """Apply all active rules to unmatched transactions.

    Returns {"matched": n, "categorized": n, "skipped": n}
    """
    today = on_date or date.today()
    rules = (
        await db.execute(
            select(BankReconciliationRule)
            .where(
                BankReconciliationRule.company_id == company_id,
                BankReconciliationRule.is_active == True,
            )
            .order_by(BankReconciliationRule.priority.asc(), BankReconciliationRule.created_at.asc())
        )
    ).scalars().all()

    matched = 0
    categorized = 0
    skipped = 0

    for rule in rules:
        txns = (
            await db.execute(
                select(BankTransaction)
                .where(
                    BankTransaction.company_id == company_id,
                    BankTransaction.status == "unmatched",
                )
                .order_by(BankTransaction.transaction_date.asc())
            )
        ).scalars().all()

        for txn in txns:
            if not _rule_matches(rule, txn):
                continue

            # date window for amount_date rules
            if rule.rule_type == "amount_date":
                window_start = txn.transaction_date - timedelta(days=rule.date_window_days)
                window_end = txn.transaction_date + timedelta(days=rule.date_window_days)
            else:
                window_start, window_end = txn.transaction_date, txn.transaction_date

            if rule.action == "categorize":
                if rule.gl_account_id is None:
                    skipped += 1
                    continue
                # Mark transaction categorized (status -> categorized)
                txn.status = "categorized"
                txn.matched_amount = txn.amount
                categorized += 1
            elif rule.action == "auto_reconcile":
                # Import reconcile helper lazily to avoid circular import
                from app.api.v1.endpoints.banking import reconcile_bank_transaction  # noqa: F401
                from app.services.bank_reconcile import auto_reconcile_transaction

                ok = await auto_reconcile_transaction(
                    db, company_id, txn, rule.gl_account_id, user_id,
                    window_start=window_start, window_end=window_end,
                )
                if ok:
                    matched += 1
                else:
                    skipped += 1

    if matched or categorized:
        await db.commit()
    return {"matched": matched, "categorized": categorized, "skipped": skipped}
