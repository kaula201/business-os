"""Database seed script for PostgreSQL."""
import asyncio
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import Base
from app.core.security import hash_password
from app.core.time import utc_now
from app.models.company import Company
from app.models.user import User
from app.models.client import Client
from app.models.product import Product, ProductCategory
from app.models.order import (
    InventoryReservation,
    Order,
    OrderFulfillment,
    OrderItem,
    OrderStatusHistory,
)
from app.models.task import Task
from app.models.warehouse import Warehouse, InventoryBalance, InventoryMovement


async def ensure_suppliers(session: AsyncSession, company_id: UUID, created_by: UUID) -> list:
    """Create demo suppliers if they don't exist."""
    from app.models.purchase import Supplier

    existing = (await session.execute(
        select(Supplier).where(Supplier.company_id == company_id)
    )).scalars().all()
    if existing:
        return existing

    suppliers_data = [
        ("SUP-001", "შპს ტექნო იმპორტი", "404123456", True, "გიორგი გიორგაძე", "+995 599 11 22 33", "info@technoimport.ge", "ქ. თბილისი, დიდუბის რაიონი", "GE12TB1234567890", 30),
        ("SUP-002", "შპს ოფის მატერიალები", "404654321", True, "ნინო ნინოშვილი", "+995 598 44 55 66", "sales@officematerials.ge", "ქ. თბილისი, საბურთალო", "GE12TB0987654321", 15),
        ("SUP-003", "ინდმეწარმე დავით მჭედლიშვილი", "01010101010", False, "დავით მჭედლიშვილი", "+995 555 77 88 99", "davit@example.ge", "ქ. ქუთაისი", None, 7),
    ]
    suppliers = []
    for code, name, ident, vat, contact, phone, email, address, bank, terms in suppliers_data:
        s = Supplier(
            company_id=company_id,
            code=code, name=name, identification_code=ident,
            is_vat_payer=vat, contact_name=contact, phone=phone,
            email=email, address=address, bank_account=bank,
            payment_terms_days=terms, is_active=True,
            created_by=created_by,
        )
        session.add(s)
        suppliers.append(s)
    await session.flush()
    return suppliers


async def ensure_purchase_orders(
    session: AsyncSession, company_id: UUID, admin_id: UUID,
    suppliers: list, products: list, warehouse_id: UUID,
):
    """Create demo purchase orders with receipts and invoices."""
    from app.models.purchase import (
        PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatusHistory,
        GoodsReceipt, GoodsReceiptItem, SupplierInvoice, SupplierInvoiceItem,
        SupplierPayable, SupplierPayment,
    )
    from app.models.order import DocumentSequence

    existing = (await session.execute(
        select(PurchaseOrder).where(PurchaseOrder.company_id == company_id)
    )).scalars().all()
    if existing:
        return

    # Ensure document sequences exist
    for doc_type in ("purchase_order", "goods_receipt", "supplier_invoice"):
        seq = await session.execute(
            select(DocumentSequence).where(
                DocumentSequence.company_id == company_id,
                DocumentSequence.document_type == doc_type,
            )
        )
        if not seq.scalar_one_or_none():
            session.add(DocumentSequence(
                company_id=company_id, document_type=doc_type, next_value=10,
            ))
    await session.flush()

    now = utc_now()

    # PO 1: Fully received and invoiced (complete workflow)
    po1 = PurchaseOrder(
        company_id=company_id, supplier_id=suppliers[0].id,
        warehouse_id=warehouse_id,
        purchase_order_number="PO-DEMO-2025-00001",
        status="received",
        expected_delivery_date=now.date() - timedelta(days=5),
        subtotal=Decimal("4500.00"), vat_amount=Decimal("810.00"),
        total=Decimal("5310.00"),
        notes="დემო: სრულად მიღებული შეკვეთა",
        created_by=admin_id, approved_by=admin_id,
        approved_at=now - timedelta(days=10),
    )
    session.add(po1)
    await session.flush()

    po1_item = PurchaseOrderItem(
        purchase_order_id=po1.id, product_id=products[0].id,
        product_name=products[0].name,
        quantity=Decimal("5"), received_quantity=Decimal("5"),
        billed_quantity=Decimal("5"),
        unit_price=Decimal("800"), discount_percent=Decimal("0"),
        vat_rate=Decimal("18"),
        line_subtotal=Decimal("4000.00"), vat_amount=Decimal("720.00"),
        line_total=Decimal("4720.00"),
    )
    session.add(po1_item)
    po1_item2 = PurchaseOrderItem(
        purchase_order_id=po1.id, product_id=products[1].id,
        product_name=products[1].name,
        quantity=Decimal("2"), received_quantity=Decimal("2"),
        billed_quantity=Decimal("2"),
        unit_price=Decimal("250"), discount_percent=Decimal("0"),
        vat_rate=Decimal("18"),
        line_subtotal=Decimal("500.00"), vat_amount=Decimal("90.00"),
        line_total=Decimal("590.00"),
    )
    session.add(po1_item2)
    await session.flush()

    for h_status in ("draft", "approved", "received"):
        session.add(PurchaseOrderStatusHistory(
            purchase_order_id=po1.id, status=h_status,
            changed_by=admin_id,
            created_at=now - timedelta(days=10 - 3 * {"draft": 0, "approved": 1, "received": 2}[h_status]),
        ))

    # Goods Receipt for PO1
    gr1 = GoodsReceipt(
        company_id=company_id, purchase_order_id=po1.id,
        warehouse_id=warehouse_id, receipt_number="GR-DEMO-2025-00001",
        idempotency_key=f"seed-gr-{po1.id}",
        status="posted", received_by=admin_id,
        notes="დემო: საქონლის მიღება",
        received_at=now - __import__("datetime").timedelta(days=3),
    )
    session.add(gr1)
    await session.flush()

    session.add(GoodsReceiptItem(
        goods_receipt_id=gr1.id, purchase_order_item_id=po1_item.id,
        product_id=products[0].id, quantity=Decimal("5"),
    ))
    session.add(GoodsReceiptItem(
        goods_receipt_id=gr1.id, purchase_order_item_id=po1_item2.id,
        product_id=products[1].id, quantity=Decimal("2"),
    ))

    # Supplier Invoice for PO1
    inv1 = SupplierInvoice(
        company_id=company_id, supplier_id=suppliers[0].id,
        purchase_order_id=po1.id,
        internal_invoice_number="SI-DEMO-2025-00001",
        supplier_invoice_number="INV-2025-001",
        invoice_date=now.date() - __import__("datetime").timedelta(days=2),
        due_date=now.date() + __import__("datetime").timedelta(days=28),
        status="approved", matching_status="matched",
        match_issues="[]",
        subtotal=Decimal("4500.00"), vat_amount=Decimal("810.00"),
        total=Decimal("5310.00"),
        notes="დემო: მომწოდებლის ინვოისი",
        created_by=admin_id, approved_by=admin_id,
        approved_at=now - __import__("datetime").timedelta(days=1),
    )
    session.add(inv1)
    await session.flush()

    session.add(SupplierInvoiceItem(
        supplier_invoice_id=inv1.id, purchase_order_item_id=po1_item.id,
        product_id=products[0].id, product_name=products[0].name,
        quantity=Decimal("5"), unit_price=Decimal("800"),
        discount_percent=Decimal("0"), vat_rate=Decimal("18"),
        line_subtotal=Decimal("4000.00"), vat_amount=Decimal("720.00"),
        line_total=Decimal("4720.00"),
        matching_status="matched",
    ))
    session.add(SupplierInvoiceItem(
        supplier_invoice_id=inv1.id, purchase_order_item_id=po1_item2.id,
        product_id=products[1].id, product_name=products[1].name,
        quantity=Decimal("2"), unit_price=Decimal("250"),
        discount_percent=Decimal("0"), vat_rate=Decimal("18"),
        line_subtotal=Decimal("500.00"), vat_amount=Decimal("90.00"),
        line_total=Decimal("590.00"),
        matching_status="matched",
    ))

    # Payable for PO1
    payable1 = SupplierPayable(
        company_id=company_id, supplier_id=suppliers[0].id,
        supplier_invoice_id=inv1.id,
        due_date=now.date() + __import__("datetime").timedelta(days=28),
        original_amount=Decimal("5310.00"), paid_amount=Decimal("0"),
        credited_amount=Decimal("0"), outstanding_amount=Decimal("5310.00"),
        status="unpaid",
    )
    session.add(payable1)

    # PO 2: Draft (not yet approved)
    po2 = PurchaseOrder(
        company_id=company_id, supplier_id=suppliers[1].id,
        warehouse_id=warehouse_id,
        purchase_order_number="PO-DEMO-2025-00002",
        status="draft",
        expected_delivery_date=now.date() + __import__("datetime").timedelta(days=14),
        subtotal=Decimal("1200.00"), vat_amount=Decimal("216.00"),
        total=Decimal("1416.00"),
        notes="დემო: მოლოდინში მყოფი შეკვეთა",
        created_by=admin_id,
    )
    session.add(po2)
    await session.flush()

    session.add(PurchaseOrderItem(
        purchase_order_id=po2.id, product_id=products[5].id,
        product_name=products[5].name,
        quantity=Decimal("50"), received_quantity=Decimal("0"),
        billed_quantity=Decimal("0"),
        unit_price=Decimal("20"), discount_percent=Decimal("0"),
        vat_rate=Decimal("18"),
        line_subtotal=Decimal("1000.00"), vat_amount=Decimal("180.00"),
        line_total=Decimal("1180.00"),
    ))
    session.add(PurchaseOrderItem(
        purchase_order_id=po2.id, product_id=products[6].id,
        product_name=products[6].name,
        quantity=Decimal("20"), received_quantity=Decimal("0"),
        billed_quantity=Decimal("0"),
        unit_price=Decimal("10"), discount_percent=Decimal("0"),
        vat_rate=Decimal("18"),
        line_subtotal=Decimal("200.00"), vat_amount=Decimal("36.00"),
        line_total=Decimal("236.00"),
    ))
    session.add(PurchaseOrderStatusHistory(
        purchase_order_id=po2.id, status="draft", changed_by=admin_id,
    ))

    # PO 3: Approved, partially received
    po3 = PurchaseOrder(
        company_id=company_id, supplier_id=suppliers[2].id,
        warehouse_id=warehouse_id,
        purchase_order_number="PO-DEMO-2025-00003",
        status="partially_received",
        expected_delivery_date=now.date() - __import__("datetime").timedelta(days=1),
        subtotal=Decimal("800.00"), vat_amount=Decimal("144.00"),
        total=Decimal("944.00"),
        notes="დემო: ნაწილობრივ მიღებული შეკვეთა",
        created_by=admin_id, approved_by=admin_id,
        approved_at=now - __import__("datetime").timedelta(days=7),
    )
    session.add(po3)
    await session.flush()

    po3_item = PurchaseOrderItem(
        purchase_order_id=po3.id, product_id=products[2].id,
        product_name=products[2].name,
        quantity=Decimal("10"), received_quantity=Decimal("5"),
        billed_quantity=Decimal("0"),
        unit_price=Decimal("80"), discount_percent=Decimal("0"),
        vat_rate=Decimal("18"),
        line_subtotal=Decimal("800.00"), vat_amount=Decimal("144.00"),
        line_total=Decimal("944.00"),
    )
    session.add(po3_item)
    await session.flush()

    for h_status in ("draft", "approved", "partially_received"):
        session.add(PurchaseOrderStatusHistory(
            purchase_order_id=po3.id, status=h_status,
            changed_by=admin_id,
        ))

    # Partial Goods Receipt for PO3
    gr3 = GoodsReceipt(
        company_id=company_id, purchase_order_id=po3.id,
        warehouse_id=warehouse_id, receipt_number="GR-DEMO-2025-00002",
        idempotency_key=f"seed-gr-{po3.id}",
        status="posted", received_by=admin_id,
        notes="დემო: ნაწილობრივი მიღება",
        received_at=now - __import__("datetime").timedelta(days=1),
    )
    session.add(gr3)
    await session.flush()

    session.add(GoodsReceiptItem(
        goods_receipt_id=gr3.id, purchase_order_item_id=po3_item.id,
        product_id=products[2].id, quantity=Decimal("5"),
    ))

    print(f"   Purchase Orders: 3 (1 complete, 1 draft, 1 partially received)")
    print(f"   Goods Receipts: 2")
    print(f"   Supplier Invoices: 1")
    print(f"   Supplier Payables: 1")


async def ensure_default_warehouses(session: AsyncSession):
    """Create one default warehouse per company and backfill legacy stock once."""
    companies = (await session.execute(select(Company))).scalars().all()
    for company in companies:
        warehouse = (
            await session.execute(
                select(Warehouse).where(
                    Warehouse.company_id == company.id,
                    Warehouse.code == "MAIN",
                )
            )
        ).scalar_one_or_none()
        if warehouse is None:
            warehouse = Warehouse(
                company_id=company.id,
                code="MAIN",
                name="მთავარი საწყობი",
                is_default=True,
            )
            session.add(warehouse)
            await session.flush()

        actor_id = (
            await session.execute(
                select(User.id).where(User.company_id == company.id).limit(1)
            )
        ).scalar_one_or_none()
        products = (
            await session.execute(
                select(Product).where(Product.company_id == company.id)
            )
        ).scalars().all()
        for product in products:
            existing_balance = (
                await session.execute(
                    select(InventoryBalance.id).where(
                        InventoryBalance.warehouse_id == warehouse.id,
                        InventoryBalance.product_id == product.id,
                    )
                )
            ).scalar_one_or_none()
            if existing_balance:
                continue

            quantity = Decimal(str(product.current_stock or 0))
            session.add(
                InventoryBalance(
                    company_id=company.id,
                    warehouse_id=warehouse.id,
                    product_id=product.id,
                    quantity=quantity,
                )
            )
            if quantity:
                session.add(
                    InventoryMovement(
                        company_id=company.id,
                        warehouse_id=warehouse.id,
                        product_id=product.id,
                        movement_type="migration_in",
                        quantity=quantity,
                        balance_after=quantity,
                        reason="legacy_stock_migration",
                        reference="MIGRATION-INITIAL-STOCK",
                        created_by=actor_id,
                    )
                )


async def ensure_order_lifecycle_backfill(session: AsyncSession):
    """Attach legacy orders to a warehouse and create idempotent reservation records."""
    orders = (
        await session.execute(
            select(Order).options(selectinload(Order.items))
        )
    ).unique().scalars().all()
    for order in orders:
        fulfillment = (
            await session.execute(
                select(OrderFulfillment).where(OrderFulfillment.order_id == order.id)
            )
        ).scalar_one_or_none()
        if fulfillment is None:
            warehouse_id = (
                await session.execute(
                    select(Warehouse.id).where(
                        Warehouse.company_id == order.company_id,
                        Warehouse.is_active.is_(True),
                        Warehouse.is_default.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if warehouse_id is None:
                continue
            fulfillment = OrderFulfillment(
                company_id=order.company_id,
                order_id=order.id,
                warehouse_id=warehouse_id,
            )
            session.add(fulfillment)
            await session.flush()

        reservation_status = {
            "confirmed": "active",
            "preparing": "active",
            "shipping": "consumed",
            "completed": "consumed",
            "cancelled": "released",
            "returned": "returned",
        }.get(order.status)
        if reservation_status is None:
            continue

        for item in order.items:
            if item.product_id is None:
                continue
            existing = (
                await session.execute(
                    select(InventoryReservation.id).where(
                        InventoryReservation.order_item_id == item.id
                    )
                )
            ).scalar_one_or_none()
            if existing:
                continue
            session.add(
                InventoryReservation(
                    company_id=order.company_id,
                    order_id=order.id,
                    order_item_id=item.id,
                    warehouse_id=fulfillment.warehouse_id,
                    product_id=item.product_id,
                    quantity=Decimal(str(item.quantity)),
                    status=reservation_status,
                )
            )


async def seed():
    from app.core.config import settings
    if not settings.allows_demo_seed():
        print(
            f"Refusing to seed demo users (admin@demo.ge / manager@demo.ge): "
            f"APP_ENV={settings.APP_ENV!r} is not development."
        )
        return
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        result = await session.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            await ensure_default_warehouses(session)
            await ensure_order_lifecycle_backfill(session)
            await session.commit()
            print("Database already seeded; warehouse and order lifecycle backfills checked.")
            return

        # Company
        company = Company(
            name="დემო კომპანია",
            identification_code="DEMO-001",
            vat_status=True,
            currency="GEL",
        )
        session.add(company)
        await session.flush()

        # Admin
        admin = User(
            company_id=company.id,
            email="admin@demo.ge",
            hashed_password=hash_password("admin123"),
            full_name="ადმინისტრატორი",
            role=User.Role.ADMIN,
            is_active=True,
        )
        session.add(admin)

        # Manager
        manager = User(
            company_id=company.id,
            email="manager@demo.ge",
            hashed_password=hash_password("manager123"),
            full_name="მენეჯერი",
            role=User.Role.MANAGER,
            is_active=True,
        )
        session.add(manager)
        await session.flush()

        # Clients
        client_data = [
            ("შპს ივერია", "legal", "404010101", True),
            ("შპს კავკასიონი", "legal", "404020202", True),
            ("გიორგი ბერიძე", "individual", "01010101010", False),
            ("შპს თბილისი ტრეიდი", "legal", "404030303", True),
            ("ნათია მაისურაძე", "individual", "02020202020", False),
        ]
        clients = []
        for name, ctype, code, vat in client_data:
            c = Client(
                company_id=company.id,
                name=name,
                client_type=ctype,
                identification_code=code,
                vat_status=vat,
                status="active",
                created_by=admin.id,
            )
            session.add(c)
            clients.append(c)
        await session.flush()

        # Categories
        cat1 = ProductCategory(company_id=company.id, name="ელექტრონიკა")
        cat2 = ProductCategory(company_id=company.id, name="ტექსტილი")
        cat3 = ProductCategory(company_id=company.id, name="საკანცელარიო")
        session.add_all([cat1, cat2, cat3])
        await session.flush()

        # Products
        products_data = [
            ("PRD-001", "ლეპტოპი Dell XPS 15", cat1.id, 4500, 3800, "ცალი", 5, 12),
            ("PRD-002", "მონიტორი LG 27\"", cat1.id, 1200, 900, "ცალი", 10, 8),
            ("PRD-003", "მაუსი Logitech MX", cat1.id, 150, 95, "ცალი", 20, 45),
            ("PRD-004", "მაისური Nike Dri-Fit", cat2.id, 65, 40, "ცალი", 30, 100),
            ("PRD-005", "ქურთუკი North Face", cat2.id, 350, 220, "ცალი", 10, 15),
            ("PRD-006", "A4 ქაღალდის კოლოფი", cat3.id, 25, 18, "ცალი", 50, 200),
            ("PRD-007", "კალამი Pilot (კოლოფი)", cat3.id, 12, 7, "ცალი", 100, 350),
            ("PRD-008", "სტიკერი Business OS", cat2.id, 5, 2.5, "ცალი", 50, 500),
        ]
        products = []
        for sku, name, cat_id, sale_price, purchase_price, unit, min_stock, stock in products_data:
            p = Product(
                company_id=company.id,
                sku=sku, name=name, category_id=cat_id,
                sale_price=sale_price, purchase_price=purchase_price,
                unit=unit, min_stock=min_stock, current_stock=stock,
            )
            session.add(p)
            products.append(p)
        await session.flush()

        # Orders
        statuses = ["new", "confirmed", "preparing"]
        for i, client in enumerate(clients[:3]):
            subtotal = (i + 1) * 500
            vat = subtotal * 0.18
            order = Order(
                company_id=company.id,
                client_id=client.id,
                order_number=f"ORD-DEMO-{i+1:05d}",
                status=statuses[i],
                subtotal=subtotal,
                vat_amount=vat,
                total=subtotal + vat,
                delivery_address=f"ქ. თბილისი, რუსთაველის გამზ. {i+1}",
                notes="დემო შეკვეთა",
                created_by=admin.id,
            )
            session.add(order)
            await session.flush()

            item = OrderItem(
                order_id=order.id,
                product_id=products[i % len(products)].id,
                quantity=i + 1,
                unit_price=500,
                total=subtotal,
                product_name=products[i % len(products)].name,
            )
            session.add(item)

            history = OrderStatusHistory(
                order_id=order.id,
                status=statuses[i],
                changed_by=admin.id,
            )
            session.add(history)

        # Tasks
        tasks_data = [
            ("კლიენტის კონტრაქტის განახლება", "todo", "high", admin.id),
            ("ყოველთვიური ანგარიშის მომზადება", "in_progress", "medium", manager.id),
            ("მარაგების ინვენტარიზაცია", "todo", "low", admin.id),
            ("მომწოდებელთან შეხვედრა", "done", "medium", manager.id),
        ]
        for title, status, priority, assigned in tasks_data:
            task = Task(
                company_id=company.id,
                title=title,
                status=status,
                priority=priority,
                assigned_to=assigned,
                created_by=admin.id,
                due_date=utc_now() + timedelta(days=7),
            )
            session.add(task)

        await ensure_default_warehouses(session)
        await ensure_order_lifecycle_backfill(session)

        # Purchase module seed data
        warehouse = (
            await session.execute(
                select(Warehouse).where(
                    Warehouse.company_id == company.id,
                    Warehouse.is_default.is_(True),
                )
            )
        ).scalar_one_or_none()
        suppliers = await ensure_suppliers(session, company.id, admin.id)
        await ensure_purchase_orders(
            session, company.id, admin.id, suppliers, products,
            warehouse.id if warehouse else (await session.execute(
                select(Warehouse).where(Warehouse.company_id == company.id)
            )).scalar_one().id,
        )

        await session.commit()
        print("✅ Database seeded successfully!")
        print(f"   Admin: admin@demo.ge / admin123")
        print(f"   Manager: manager@demo.ge / manager123")
        print(f"   Clients: {len(clients)}, Products: {len(products)}, Orders: 3, Tasks: 4")
        print(f"   Suppliers: {len(suppliers)}, Purchase Orders: 3, Goods Receipts: 2, Supplier Invoices: 1")


if __name__ == "__main__":
    asyncio.run(seed())