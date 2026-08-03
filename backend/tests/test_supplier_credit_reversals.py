import asyncio
from datetime import date

import pytest

from app.core.security import hash_password
from app.models.company import Company
from app.models.user import User
from tests.test_supplier_payables import create_supplier_invoice, setup_received_purchase


async def create_approved_payable(
    client, auth_headers, test_company, db_session, suffix: str
):
    supplier, purchase_order = await setup_received_purchase(
        client, auth_headers, test_company, db_session, suffix
    )
    invoice = await create_supplier_invoice(
        client, auth_headers, supplier, purchase_order, suffix
    )
    approved = await client.patch(
        f"/api/v1/supplier-invoices/{invoice['id']}/status",
        json={"status": "approved", "notes": "Finance approval"},
        headers=auth_headers,
    )
    assert approved.status_code == 200, approved.text
    return approved.json()["data"]["payable"]


async def create_user_headers(client, db_session, company_id, email: str, role: str):
    password = "finance-test-123"
    user = User(
        company_id=company_id,
        email=email,
        hashed_password=hash_password(password),
        full_name="Finance Test User",
        role=role,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_credit_note_reduces_payable_and_is_idempotent(
    client, auth_headers, test_company, db_session
):
    payable = await create_approved_payable(
        client, auth_headers, test_company, db_session, "CREDIT"
    )

    payload = {
        "idempotency_key": "credit-note-one",
        "supplier_credit_note_number": "CN-001",
        "amount": 30,
        "credit_date": str(date.today()),
        "reason": "მომწოდებლის ფასდაკლება",
    }
    created = await client.post(
        f"/api/v1/supplier-payables/{payable['id']}/credit-notes",
        json=payload,
        headers=auth_headers,
    )
    assert created.status_code == 200, created.text
    credited = created.json()["data"]
    assert credited["original_amount"] == 100
    assert credited["paid_amount"] == 0
    assert credited["credited_amount"] == 30
    assert credited["outstanding_amount"] == 70
    assert credited["status"] == "unpaid"
    assert len(credited["credit_notes"]) == 1
    assert credited["credit_notes"][0]["supplier_credit_note_number"] == "CN-001"

    duplicate = await client.post(
        f"/api/v1/supplier-payables/{payable['id']}/credit-notes",
        json=payload,
        headers=auth_headers,
    )
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["data"]["credited_amount"] == 30
    assert len(duplicate.json()["data"]["credit_notes"]) == 1

    over_credit = await client.post(
        f"/api/v1/supplier-payables/{payable['id']}/credit-notes",
        json={**payload, "idempotency_key": "credit-note-over", "amount": 71},
        headers=auth_headers,
    )
    assert over_credit.status_code == 409


@pytest.mark.asyncio
async def test_payment_reversal_restores_payable_and_cannot_repeat(
    client, auth_headers, test_company, db_session
):
    payable = await create_approved_payable(
        client, auth_headers, test_company, db_session, "REVERSAL"
    )
    paid = await client.post(
        f"/api/v1/supplier-payables/{payable['id']}/payments",
        json={
            "idempotency_key": "payment-to-reverse",
            "amount": 100,
            "payment_date": str(date.today()),
            "payment_method": "bank_transfer",
            "reference": "BANK-REV-1",
        },
        headers=auth_headers,
    )
    assert paid.status_code == 200, paid.text
    payment = paid.json()["data"]["payments"][0]

    payload = {
        "idempotency_key": "reversal-one",
        "reason": "გადახდა არასწორ ანგარიშზე დაფიქსირდა",
    }
    reversed_response = await client.post(
        f"/api/v1/supplier-payments/{payment['id']}/reversal",
        json=payload,
        headers=auth_headers,
    )
    assert reversed_response.status_code == 200, reversed_response.text
    restored = reversed_response.json()["data"]
    assert restored["paid_amount"] == 0
    assert restored["credited_amount"] == 0
    assert restored["outstanding_amount"] == 100
    assert restored["status"] == "unpaid"
    assert restored["payments"][0]["is_reversed"] is True
    assert restored["payments"][0]["reversal"]["reason"] == payload["reason"]

    duplicate = await client.post(
        f"/api/v1/supplier-payments/{payment['id']}/reversal",
        json=payload,
        headers=auth_headers,
    )
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["data"]["paid_amount"] == 0

    second_reversal = await client.post(
        f"/api/v1/supplier-payments/{payment['id']}/reversal",
        json={"idempotency_key": "reversal-two", "reason": "მეორე მცდელობა"},
        headers=auth_headers,
    )
    assert second_reversal.status_code == 409


@pytest.mark.asyncio
async def test_credit_and_payment_reversal_keep_decimal_balance_consistent(
    client, auth_headers, test_company, db_session
):
    payable = await create_approved_payable(
        client, auth_headers, test_company, db_session, "COMBINED"
    )
    paid = await client.post(
        f"/api/v1/supplier-payables/{payable['id']}/payments",
        json={
            "idempotency_key": "combined-payment",
            "amount": 40,
            "payment_date": str(date.today()),
            "payment_method": "bank_transfer",
        },
        headers=auth_headers,
    )
    assert paid.status_code == 200
    payment = paid.json()["data"]["payments"][0]

    credit = await client.post(
        f"/api/v1/supplier-payables/{payable['id']}/credit-notes",
        json={
            "idempotency_key": "combined-credit",
            "supplier_credit_note_number": "CN-COMBINED",
            "amount": 20,
            "credit_date": str(date.today()),
            "reason": "კორექტირება",
        },
        headers=auth_headers,
    )
    assert credit.status_code == 200, credit.text
    assert credit.json()["data"]["outstanding_amount"] == 40

    reversal = await client.post(
        f"/api/v1/supplier-payments/{payment['id']}/reversal",
        json={"idempotency_key": "combined-reversal", "reason": "ბანკმა დააბრუნა"},
        headers=auth_headers,
    )
    assert reversal.status_code == 200, reversal.text
    result = reversal.json()["data"]
    assert result["original_amount"] == 100
    assert result["paid_amount"] == 0
    assert result["credited_amount"] == 20
    assert result["outstanding_amount"] == 80
    assert result["status"] == "unpaid"


@pytest.mark.asyncio
async def test_concurrent_credit_notes_cannot_over_credit_payable(
    client, auth_headers, test_company, db_session
):
    payable = await create_approved_payable(
        client, auth_headers, test_company, db_session, "CREDIT-CONCURRENT"
    )

    async def credit(key: str, number: str):
        return await client.post(
            f"/api/v1/supplier-payables/{payable['id']}/credit-notes",
            json={
                "idempotency_key": key,
                "supplier_credit_note_number": number,
                "amount": 70,
                "credit_date": str(date.today()),
                "reason": "Concurrent credit test",
            },
            headers=auth_headers,
        )

    responses = await asyncio.gather(
        credit("credit-concurrent-a", "CN-CON-A"),
        credit("credit-concurrent-b", "CN-CON-B"),
    )
    assert sorted(response.status_code for response in responses) == [200, 409]

    current = await client.get(
        f"/api/v1/supplier-payables/{payable['id']}", headers=auth_headers
    )
    assert current.status_code == 200
    data = current.json()["data"]
    assert data["credited_amount"] == 70
    assert data["outstanding_amount"] == 30
    assert len(data["credit_notes"]) == 1


@pytest.mark.asyncio
async def test_credit_note_permissions_and_tenant_isolation(
    client, auth_headers, test_company, db_session
):
    payable = await create_approved_payable(
        client, auth_headers, test_company, db_session, "AUTH-TENANT"
    )
    payload = {
        "idempotency_key": "credit-auth-test",
        "supplier_credit_note_number": "CN-AUTH-1",
        "amount": 10,
        "credit_date": str(date.today()),
        "reason": "Authorization test",
    }

    employee_headers = await create_user_headers(
        client, db_session, test_company.id, "employee-finance@test.ge", User.Role.EMPLOYEE
    )
    forbidden = await client.post(
        f"/api/v1/supplier-payables/{payable['id']}/credit-notes",
        json=payload,
        headers=employee_headers,
    )
    assert forbidden.status_code == 403

    other_company = Company(
        name="Other Tenant",
        identification_code="OTHER-TENANT-001",
        vat_status=True,
        currency="GEL",
    )
    db_session.add(other_company)
    await db_session.commit()
    await db_session.refresh(other_company)
    other_admin_headers = await create_user_headers(
        client, db_session, other_company.id, "other-admin@test.ge", User.Role.ADMIN
    )
    hidden = await client.post(
        f"/api/v1/supplier-payables/{payable['id']}/credit-notes",
        json={**payload, "idempotency_key": "credit-other-tenant"},
        headers=other_admin_headers,
    )
    assert hidden.status_code == 404
