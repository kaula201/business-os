import io
import json
import zipfile
from datetime import date, timedelta
from decimal import Decimal

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.models.client import Client
from app.models.audit import AuditLog
from app.models.company import Company
from app.models.gl import JournalEntry
from app.models.invoice import Invoice
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.receivable import CustomerReceivable
from app.models.user import User
from tests.test_supplier_credit_reversals import create_user_headers


async def create_invoice_order(client, auth_headers, test_company, db_session, suffix: str, status: str = "confirmed"):
    customer = Client(
        company_id=test_company.id,
        name=f"Invoice Customer {suffix}",
        client_type="legal",
        identification_code=f"INV-CUST-{suffix}",
        vat_status=True,
        address="თბილისი, თავისუფლების მოედანი 1",
        status="active",
    )
    product = Product(
        company_id=test_company.id,
        sku=f"INV-SKU-{suffix}",
        name=f"Invoice Product {suffix}",
        sale_price=Decimal("100.00"),
        current_stock=20,
    )
    db_session.add_all([customer, product])
    await db_session.commit()
    await db_session.refresh(customer)
    await db_session.refresh(product)
    response = await client.post(
        "/api/v1/orders/",
        json={
            "client_id": str(customer.id),
            "items": [{
                "product_id": str(product.id),
                "product_name": product.name,
                "quantity": 2,
                "unit_price": 100,
                "discount_percent": 10,
            }],
            "delivery_address": customer.address,
            "notes": f"Invoice order {suffix}",
            "is_vat_payer": True,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    order_id = response.json()["data"]["id"]
    order = (await db_session.execute(select(Order).where(Order.id == order_id))).scalar_one()
    order.status = status
    await db_session.commit()
    return response.json()["data"], customer, product


def invoice_payload(order_id: str, suffix: str):
    today = date.today()
    return {
        "order_id": order_id,
        "idempotency_key": f"invoice-generation-{suffix}",
        "invoice_date": today.isoformat(),
        "due_date": (today + timedelta(days=14)).isoformat(),
        "notes": "გადახდის ვადა 14 დღე",
    }


@pytest.mark.asyncio
async def test_order_creation_automatically_creates_editable_invoice_draft_without_receivable(
    client, auth_headers, test_company, db_session
):
    order, _, _ = await create_invoice_order(
        client, auth_headers, test_company, db_session, "AUTO-DRAFT", status="new"
    )
    invoice = (
        await db_session.execute(select(Invoice).where(Invoice.order_id == order["id"]))
    ).scalar_one_or_none()
    assert invoice is not None
    assert invoice.status == "draft"
    receivable = (
        await db_session.execute(
            select(CustomerReceivable).where(CustomerReceivable.invoice_id == invoice.id)
        )
    ).scalar_one_or_none()
    assert receivable is None


@pytest.mark.asyncio
async def test_invoice_draft_can_be_edited_and_recalculates_totals(
    client, auth_headers, test_company, db_session
):
    order, _, _ = await create_invoice_order(
        client, auth_headers, test_company, db_session, "EDIT-DRAFT", status="new"
    )
    invoice = (
        await db_session.execute(select(Invoice).where(Invoice.order_id == order["id"]))
    ).scalar_one()
    response = await client.patch(
        f"/api/v1/invoices/{invoice.id}/draft",
        headers=auth_headers,
        json={
            "invoice_date": "2026-07-30",
            "due_date": "2026-08-15",
            "currency": "GEL",
            "seller_name": "განახლებული კომპანია",
            "seller_identification_code": "UPDATED-SELLER",
            "seller_address": "თბილისი",
            "seller_phone": "+995555000000",
            "seller_email": "seller@example.ge",
            "client_name": "განახლებული მყიდველი",
            "client_identification_code": "UPDATED-BUYER",
            "client_address": "ბათუმი",
            "notes": "რედაქტირებული შაბლონი",
            "items": [{
                "product_name": "რედაქტირებული პროდუქტი",
                "quantity": 3,
                "unit_price": 120,
                "discount_percent": 10,
                "vat_rate": 18,
            }],
        },
    )
    assert response.status_code == 200, response.text
    draft = response.json()["data"]
    assert draft["status"] == "draft"
    assert draft["seller_name"] == "განახლებული კომპანია"
    assert draft["client_name"] == "განახლებული მყიდველი"
    assert draft["subtotal"] == 324
    assert draft["vat_amount"] == 58.32
    assert draft["total"] == 382.32

    audit = (
        await db_session.execute(
            select(AuditLog)
            .where(
                AuditLog.entity_id == invoice.id,
                AuditLog.action == "customer_invoice.draft_updated",
            )
            .order_by(AuditLog.created_at.desc())
        )
    ).scalars().first()
    details = json.loads(audit.details)
    assert details["before"]["items"][0]["product_name"] == "Invoice Product EDIT-DRAFT"
    assert details["after"]["items"][0]["product_name"] == "რედაქტირებული პროდუქტი"
    assert details["after"]["total"] == "382.32"
    assert draft["items"][0]["line_total"] == 382.32


@pytest.mark.asyncio
async def test_issuing_draft_creates_one_receivable_and_one_gl_entry_idempotently(
    client, auth_headers, test_company, db_session
):
    order, _, _ = await create_invoice_order(
        client, auth_headers, test_company, db_session, "ISSUE-DRAFT", status="new"
    )
    invoice = (
        await db_session.execute(select(Invoice).where(Invoice.order_id == order["id"]))
    ).scalar_one()
    issued = await client.post(f"/api/v1/invoices/{invoice.id}/issue", headers=auth_headers)
    assert issued.status_code == 200, issued.text
    assert issued.json()["data"]["status"] == "issued"

    receivables = (
        await db_session.execute(
            select(CustomerReceivable).where(CustomerReceivable.invoice_id == invoice.id)
        )
    ).scalars().all()
    entries = (
        await db_session.execute(
            select(JournalEntry).where(
                JournalEntry.reference_type == "invoice",
                JournalEntry.reference_id == invoice.id,
            )
        )
    ).scalars().all()
    assert len(receivables) == 1
    assert len(entries) == 1

    replay = await client.post(f"/api/v1/invoices/{invoice.id}/issue", headers=auth_headers)
    assert replay.status_code == 200
    assert replay.json()["data"]["id"] == str(invoice.id)
    receivable_count = (
        await db_session.execute(
            select(CustomerReceivable).where(CustomerReceivable.invoice_id == invoice.id)
        )
    ).scalars().all()
    assert len(receivable_count) == 1


@pytest.mark.asyncio
async def test_issued_invoice_exports_pdf_word_and_excel_while_draft_is_preview_only(
    client, auth_headers, test_company, db_session
):
    order, _, _ = await create_invoice_order(
        client, auth_headers, test_company, db_session, "EXPORTS", status="new"
    )
    invoice = (
        await db_session.execute(select(Invoice).where(Invoice.order_id == order["id"]))
    ).scalar_one()

    draft_pdf = await client.get(f"/api/v1/invoices/{invoice.id}/download", headers=auth_headers)
    assert draft_pdf.status_code == 409
    draft_preview = await client.get(f"/api/v1/invoices/{invoice.id}/preview", headers=auth_headers)
    assert draft_preview.status_code == 200

    issued = await client.post(f"/api/v1/invoices/{invoice.id}/issue", headers=auth_headers)
    assert issued.status_code == 200
    pdf = await client.get(f"/api/v1/invoices/{invoice.id}/download", headers=auth_headers)
    word = await client.get(f"/api/v1/invoices/{invoice.id}/download-word", headers=auth_headers)
    excel = await client.get(f"/api/v1/invoices/{invoice.id}/download-excel", headers=auth_headers)

    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert word.status_code == 200 and word.content.startswith(b"PK")
    assert excel.status_code == 200 and excel.content.startswith(b"PK")
    assert "wordprocessingml.document" in word.headers["content-type"]
    assert "spreadsheetml.sheet" in excel.headers["content-type"]

    with zipfile.ZipFile(io.BytesIO(word.content)) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
        assert "ინვოისი" in document_xml
        assert "Invoice Product EXPORTS" in document_xml

    workbook = load_workbook(io.BytesIO(excel.content), data_only=False)
    worksheet = workbook["ინვოისი"]
    assert str(worksheet["A1"].value).startswith("ინვოისი №")
    assert worksheet["B9"].value == "Invoice Product EXPORTS"
    assert str(worksheet["G9"].value).startswith("=ROUND(")
    assert str(worksheet["H9"].value).startswith("=ROUND(")


@pytest.mark.asyncio
async def test_generate_invoice_creates_immutable_decimal_snapshot(
    client, auth_headers, test_company, db_session
):
    order, customer, product = await create_invoice_order(
        client, auth_headers, test_company, db_session, "SNAPSHOT"
    )
    response = await client.post(
        "/api/v1/invoices/generate",
        json=invoice_payload(order["id"], "SNAPSHOT"),
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    invoice = response.json()["data"]
    assert invoice["invoice_number"].startswith("INV-")
    assert invoice["order_id"] == order["id"]
    assert invoice["order_number"] == order["order_number"]
    assert invoice["status"] == "issued"
    assert invoice["seller_name"] == test_company.name
    assert invoice["seller_identification_code"] == test_company.identification_code
    assert invoice["client_name"] == customer.name
    assert invoice["client_identification_code"] == customer.identification_code
    assert invoice["subtotal"] == 180
    assert invoice["vat_amount"] == 32.4
    assert invoice["total"] == 212.4
    assert invoice["currency"] == "GEL"
    assert len(invoice["items"]) == 1
    assert invoice["items"][0]["product_name"] == product.name
    assert invoice["items"][0]["quantity"] == 2
    assert invoice["items"][0]["unit_price"] == 100
    assert invoice["items"][0]["discount_percent"] == 10
    assert invoice["items"][0]["line_subtotal"] == 180
    assert invoice["items"][0]["vat_amount"] == 32.4
    assert invoice["items"][0]["line_total"] == 212.4

    # Changing source records must not alter the issued invoice snapshot.
    customer.name = "Changed Customer"
    order_row = (await db_session.execute(select(Order).where(Order.id == order["id"]))).scalar_one()
    item_row = (await db_session.execute(select(OrderItem).where(OrderItem.order_id == order["id"]))).scalar_one()
    order_row.total = 9999
    item_row.product_name = "Changed Product"
    await db_session.commit()

    detail = await client.get(f"/api/v1/invoices/{invoice['id']}", headers=auth_headers)
    assert detail.status_code == 200, detail.text
    immutable = detail.json()["data"]
    assert immutable["client_name"] == f"Invoice Customer SNAPSHOT"
    assert immutable["items"][0]["product_name"] == f"Invoice Product SNAPSHOT"
    assert immutable["total"] == 212.4


@pytest.mark.asyncio
async def test_invoice_generation_is_idempotent_and_one_invoice_per_order(
    client, auth_headers, test_company, db_session
):
    order, _, _ = await create_invoice_order(client, auth_headers, test_company, db_session, "IDEMPOTENT")
    payload = invoice_payload(order["id"], "IDEMPOTENT")
    first = await client.post("/api/v1/invoices/generate", json=payload, headers=auth_headers)
    assert first.status_code == 200, first.text
    duplicate = await client.post("/api/v1/invoices/generate", json=payload, headers=auth_headers)
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["id"] == first.json()["data"]["id"]

    second_key = await client.post(
        "/api/v1/invoices/generate",
        json={**payload, "idempotency_key": "different-key-same-order"},
        headers=auth_headers,
    )
    assert second_key.status_code == 409


@pytest.mark.asyncio
async def test_invoice_list_and_pdf_download_use_tenant_scoped_snapshot(
    client, auth_headers, test_company, db_session
):
    order, _, _ = await create_invoice_order(client, auth_headers, test_company, db_session, "PDF")
    generated = await client.post(
        "/api/v1/invoices/generate",
        json=invoice_payload(order["id"], "PDF"),
        headers=auth_headers,
    )
    assert generated.status_code == 200, generated.text
    invoice = generated.json()["data"]

    listing = await client.get("/api/v1/invoices/?page_size=100", headers=auth_headers)
    assert listing.status_code == 200, listing.text
    assert any(row["id"] == invoice["id"] for row in listing.json()["data"]["items"])

    pdf = await client.get(f"/api/v1/invoices/{invoice['id']}/download", headers=auth_headers)
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF")
    assert b"DejaVuSans" in pdf.content
    assert invoice["invoice_number"] in pdf.headers["content-disposition"]


@pytest.mark.asyncio
async def test_invoice_preview_returns_inline_pdf_template(
    client, auth_headers, test_company, db_session
):
    order, _, _ = await create_invoice_order(
        client, auth_headers, test_company, db_session, "PREVIEW"
    )
    generated = await client.post(
        "/api/v1/invoices/generate",
        json=invoice_payload(order["id"], "PREVIEW"),
        headers=auth_headers,
    )
    assert generated.status_code == 200, generated.text
    invoice = generated.json()["data"]

    preview = await client.get(
        f"/api/v1/invoices/{invoice['id']}/preview",
        headers=auth_headers,
    )
    assert preview.status_code == 200, preview.text
    assert preview.headers["content-type"].startswith("application/pdf")
    assert preview.headers["content-disposition"].startswith("inline;")
    assert preview.content.startswith(b"%PDF")
    assert b"DejaVuSans" in preview.content


@pytest.mark.asyncio
async def test_invoice_generation_rejects_draft_cross_tenant_and_employee(
    client, auth_headers, test_company, db_session
):
    draft_order, _, _ = await create_invoice_order(
        client, auth_headers, test_company, db_session, "DRAFT", status="new"
    )
    draft = await client.post(
        "/api/v1/invoices/generate",
        json=invoice_payload(draft_order["id"], "DRAFT"),
        headers=auth_headers,
    )
    assert draft.status_code == 409

    employee_headers = await create_user_headers(
        client, db_session, test_company.id, "invoice-employee@test.ge", User.Role.EMPLOYEE
    )
    forbidden = await client.post(
        "/api/v1/invoices/generate",
        json=invoice_payload(draft_order["id"], "EMPLOYEE"),
        headers=employee_headers,
    )
    assert forbidden.status_code == 403

    other_company = Company(
        name="Other Invoice Company",
        identification_code="OTHER-INVOICE-COMPANY",
        currency="GEL",
    )
    db_session.add(other_company)
    await db_session.flush()
    other_client = Client(
        company_id=other_company.id,
        name="Other Tenant Customer",
        client_type="legal",
        identification_code="OTHER-TENANT-CUSTOMER",
        status="active",
    )
    db_session.add(other_client)
    await db_session.flush()
    other_order = Order(
        company_id=other_company.id,
        client_id=other_client.id,
        order_number="ORD-OTHER-INVOICE",
        status="confirmed",
        subtotal=100,
        vat_amount=18,
        total=118,
    )
    db_session.add(other_order)
    await db_session.commit()
    cross_tenant = await client.post(
        "/api/v1/invoices/generate",
        json=invoice_payload(str(other_order.id), "CROSS-TENANT"),
        headers=auth_headers,
    )
    assert cross_tenant.status_code == 404
