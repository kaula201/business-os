import json
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.time import utc_now
from app.models.audit import AuditLog
from app.models.order import DocumentSequence
from app.models.product import Product
from app.models.procurement import BlanketOrder, BlanketOrderLine
from app.models.purchase import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatusHistory,
    PurchaseCostHistory,
    PurchaseApprovalPolicy,
    ScheduledDelivery,
    PurchaseOrderBackorder,
    PurchaseReturn,
    PurchaseReturnItem,
    PurchaseOrderAmendment,
    Supplier,
    SupplierInvoice,
    SupplierInvoiceItem,
)
from app.models.user import User
from app.models.warehouse import InventoryBalance, InventoryMovement, Warehouse
from app.schemas.common import PaginatedResponse, ResponseBase
from app.services.fiscal import resolve_fiscal_position
from app.schemas.purchase import (
    ApprovalLimitInfo,
    GoodsReceiptCreate,
    GoodsReceiptItemResponse,
    GoodsReceiptResponse,
    PurchaseOrderCreate,
    PurchaseOrderHistoryResponse,
    PurchaseOrderItemResponse,
    PurchaseOrderResponse,
    PurchaseOrderStatusChange,
    PurchaseWorkflowResponse,
    ThreeWayMatchSummary,
)

router = APIRouter(prefix="/purchase-orders", tags=["შესყიდვები"])

PO_TRANSITIONS = {
    "draft": {"approved", "cancelled"},
    "approved": {"cancelled"},
    "partially_received": set(),
    "received": set(),
    "cancelled": set(),
}

PO_LOAD_OPTIONS = (
    selectinload(PurchaseOrder.supplier),
    selectinload(PurchaseOrder.warehouse),
    selectinload(PurchaseOrder.items),
)

RECEIPT_LOAD_OPTIONS = (
    selectinload(GoodsReceipt.warehouse),
    selectinload(GoodsReceipt.purchase_order),
    selectinload(GoodsReceipt.items).selectinload(GoodsReceiptItem.product),
)


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def cost(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


async def allocate_document_number(
    db: AsyncSession,
    company_id: UUID,
    document_type: str,
    prefix: str,
) -> str:
    key = f"{company_id}:{document_type}"
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key}
    )
    sequence = (
        await db.execute(
            select(DocumentSequence)
            .where(
                DocumentSequence.company_id == company_id,
                DocumentSequence.document_type == document_type,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if sequence is None:
        allocated = 1
        sequence = DocumentSequence(
            company_id=company_id,
            document_type=document_type,
            next_value=2,
        )
        db.add(sequence)
    else:
        allocated = sequence.next_value
        sequence.next_value += 1
    return f"{prefix}-{utc_now().year}-{allocated:05d}"


def add_audit(
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


DEFAULT_MANAGER_APPROVAL_LIMIT = Decimal("5000.00")


async def get_manager_approval_limit(db: AsyncSession, company_id: UUID) -> Decimal:
    value = (
        await db.execute(
            select(PurchaseApprovalPolicy.manager_approval_limit).where(
                PurchaseApprovalPolicy.company_id == company_id
            )
        )
    ).scalar_one_or_none()
    return Decimal(value) if value is not None else DEFAULT_MANAGER_APPROVAL_LIMIT


def required_approval_role(total: Decimal, manager_limit: Decimal) -> str:
    return "manager" if Decimal(total) <= manager_limit else "admin"


def build_purchase_order_response(order: PurchaseOrder, manager_limit: Decimal) -> PurchaseOrderResponse:
    return PurchaseOrderResponse(
        id=order.id,
        supplier_id=order.supplier_id,
        supplier_name=order.supplier.name,
        warehouse_id=order.warehouse_id,
        warehouse_name=order.warehouse.name,
        purchase_order_number=order.purchase_order_number,
        status=order.status,
        version=order.version,
        expected_delivery_date=order.expected_delivery_date,
        subtotal=float(order.subtotal),
        vat_amount=float(order.vat_amount),
        total=float(order.total),
        notes=order.notes,
        approved_at=order.approved_at,
        approved_by=order.approved_by,
        required_approval_role=required_approval_role(order.total, manager_limit),
        items=[
            PurchaseOrderItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=float(item.quantity),
                received_quantity=float(item.received_quantity),
                billed_quantity=float(item.billed_quantity),
                remaining_quantity=float(item.quantity - item.received_quantity),
                remaining_to_bill=float(item.quantity - item.billed_quantity),
                unit_price=float(item.unit_price),
                discount_percent=float(item.discount_percent),
                vat_rate=float(item.vat_rate),
                line_subtotal=float(item.line_subtotal),
                vat_amount=float(item.vat_amount),
                line_total=float(item.line_total),
            )
            for item in order.items
        ],
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def build_receipt_response(receipt: GoodsReceipt) -> GoodsReceiptResponse:
    return GoodsReceiptResponse(
        id=receipt.id,
        purchase_order_id=receipt.purchase_order_id,
        receipt_number=receipt.receipt_number,
        warehouse_id=receipt.warehouse_id,
        warehouse_name=receipt.warehouse.name,
        idempotency_key=receipt.idempotency_key,
        status=receipt.status,
        purchase_order_status=receipt.purchase_order.status,
        notes=receipt.notes,
        received_at=receipt.received_at,
        quality_status=receipt.quality_status,
        quality_notes=receipt.quality_notes,
        items=[
            GoodsReceiptItemResponse(
                id=item.id,
                purchase_order_item_id=item.purchase_order_item_id,
                product_id=item.product_id,
                product_name=item.product.name,
                quantity=float(item.quantity),
            )
            for item in receipt.items
        ],
    )


async def load_purchase_order(
    db: AsyncSession,
    purchase_order_id: UUID,
    company_id: UUID,
    *,
    for_update: bool = False,
) -> PurchaseOrder:
    query = select(PurchaseOrder).where(
        PurchaseOrder.id == purchase_order_id,
        PurchaseOrder.company_id == company_id,
    )
    if for_update:
        query = query.with_for_update()
    query = query.options(*PO_LOAD_OPTIONS)
    order = (await db.execute(query)).unique().scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Purchase Order არ მოიძებნა")
    return order


async def load_receipt_by_idempotency(
    db: AsyncSession, company_id: UUID, idempotency_key: str
) -> GoodsReceipt | None:
    return (
        await db.execute(
            select(GoodsReceipt)
            .where(
                GoodsReceipt.company_id == company_id,
                GoodsReceipt.idempotency_key == idempotency_key,
            )
            .options(*RECEIPT_LOAD_OPTIONS)
        )
    ).unique().scalar_one_or_none()


@router.get("/", response_model=ResponseBase[PaginatedResponse[PurchaseOrderResponse]])
async def list_purchase_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    supplier_id: UUID | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [PurchaseOrder.company_id == current_user.company_id]
    if status:
        filters.append(PurchaseOrder.status == status)
    if supplier_id:
        filters.append(PurchaseOrder.supplier_id == supplier_id)
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                PurchaseOrder.purchase_order_number.ilike(pattern),
                PurchaseOrder.notes.ilike(pattern),
            )
        )

    total = (
        await db.execute(select(func.count(PurchaseOrder.id)).where(*filters))
    ).scalar_one()
    orders = (
        await db.execute(
            select(PurchaseOrder)
            .where(*filters)
            .options(*PO_LOAD_OPTIONS)
            .order_by(PurchaseOrder.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).unique().scalars().all()
    manager_limit = await get_manager_approval_limit(db, current_user.company_id)
    return ResponseBase(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=[build_purchase_order_response(order, manager_limit) for order in orders],
        )
    )


@router.post("/", response_model=ResponseBase[PurchaseOrderResponse])
async def create_purchase_order(
    data: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = (
        await db.execute(
            select(Supplier).where(
                Supplier.id == data.supplier_id,
                Supplier.company_id == current_user.company_id,
                Supplier.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="აქტიური მომწოდებელი არ მოიძებნა")

    warehouse = (
        await db.execute(
            select(Warehouse).where(
                Warehouse.id == data.warehouse_id,
                Warehouse.company_id == current_user.company_id,
                Warehouse.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not warehouse:
        raise HTTPException(status_code=404, detail="აქტიური საწყობი არ მოიძებნა")

    product_ids = [item.product_id for item in data.items]
    products = (
        await db.execute(
            select(Product).where(
                Product.id.in_(product_ids),
                Product.company_id == current_user.company_id,
                Product.is_active.is_(True),
            )
        )
    ).scalars().all()
    product_map = {product.id: product for product in products}
    if len(product_map) != len(product_ids):
        raise HTTPException(status_code=404, detail="ერთი ან მეტი პროდუქტი არ მოიძებნა")

    number = await allocate_document_number(
        db, current_user.company_id, "purchase_order", "PO"
    )
    fiscal = await resolve_fiscal_position(
        db, current_user.company_id,
        partner_fiscal_position_id=supplier.fiscal_position_id,
        applies_to="purchase",
    )
    # Preserve legacy non-VAT suppliers unless an explicit fiscal position says otherwise.
    po_vat_rate = fiscal.vat_rate if (supplier.fiscal_position_id or supplier.is_vat_payer) else Decimal("0.0000")
    order = PurchaseOrder(
        company_id=current_user.company_id,
        supplier_id=supplier.id,
        fiscal_position_id=fiscal.id,
        warehouse_id=warehouse.id,
        purchase_order_number=number,
        status="draft",
        expected_delivery_date=data.expected_delivery_date,
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(order)
    await db.flush()

    subtotal = Decimal("0")
    vat_amount = Decimal("0")
    total = Decimal("0")
    # Active blanket orders for this supplier, to auto-apply agreed prices.
    blanket_lines = (await db.execute(
        select(BlanketOrderLine)
        .join(BlanketOrder, BlanketOrder.id == BlanketOrderLine.blanket_order_id)
        .where(
            BlanketOrder.company_id == current_user.company_id,
            BlanketOrder.supplier_id == supplier.id,
            BlanketOrder.status == "active",
            BlanketOrderLine.product_id.in_(product_ids),
        )
    )).scalars().all()
    blanket_by_product = {bl.product_id: bl for bl in blanket_lines}
    for item_data in data.items:
        blanket_line = blanket_by_product.get(item_data.product_id)
        unit_price = blanket_line.unit_price if blanket_line else item_data.unit_price
        gross = item_data.quantity * unit_price
        discount = gross * item_data.discount_percent / Decimal("100")
        line_subtotal = money(gross - discount)
        line_vat = money(line_subtotal * po_vat_rate / Decimal("100"))
        line_total = money(line_subtotal + line_vat)
        item = PurchaseOrderItem(
            purchase_order_id=order.id,
            product_id=item_data.product_id,
            product_name=product_map[item_data.product_id].name,
            quantity=item_data.quantity,
            received_quantity=Decimal("0"),
            unit_price=unit_price,
            discount_percent=item_data.discount_percent,
            vat_rate=po_vat_rate,
            line_subtotal=line_subtotal,
            vat_amount=line_vat,
            line_total=line_total,
        )
        db.add(item)
        # Consume the blanket-order line quantity.
        if blanket_line:
            blanket_line.used_quantity += item_data.quantity
        subtotal += line_subtotal
        vat_amount += line_vat
        total += line_total

    order.subtotal = money(subtotal)
    order.vat_amount = money(vat_amount)
    order.total = money(total)
    db.add(
        PurchaseOrderStatusHistory(
            purchase_order_id=order.id,
            status="draft",
            changed_by=current_user.id,
        )
    )
    await db.flush()
    add_audit(
        db,
        current_user,
        "purchase_order.created",
        "purchase_order",
        order.id,
        {"purchase_order_number": number, "supplier_id": supplier.id, "total": order.total},
    )
    order = await load_purchase_order(db, order.id, current_user.company_id)
    manager_limit = await get_manager_approval_limit(db, current_user.company_id)
    return ResponseBase(data=build_purchase_order_response(order, manager_limit))


@router.get("/{purchase_order_id}", response_model=ResponseBase[PurchaseOrderResponse])
async def get_purchase_order(
    purchase_order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await load_purchase_order(db, purchase_order_id, current_user.company_id)
    manager_limit = await get_manager_approval_limit(db, current_user.company_id)
    return ResponseBase(data=build_purchase_order_response(order, manager_limit))


@router.get(
    "/{purchase_order_id}/history",
    response_model=ResponseBase[list[PurchaseOrderHistoryResponse]],
)
async def get_purchase_order_history(
    purchase_order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await load_purchase_order(db, purchase_order_id, current_user.company_id)
    history = (
        await db.execute(
            select(PurchaseOrderStatusHistory)
            .where(PurchaseOrderStatusHistory.purchase_order_id == purchase_order_id)
            .order_by(PurchaseOrderStatusHistory.created_at, PurchaseOrderStatusHistory.id)
        )
    ).scalars().all()
    return ResponseBase(
        data=[PurchaseOrderHistoryResponse.model_validate(item) for item in history]
    )


@router.patch(
    "/{purchase_order_id}/status",
    response_model=ResponseBase[PurchaseOrderResponse],
)
async def change_purchase_order_status(
    purchase_order_id: UUID,
    data: PurchaseOrderStatusChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await load_purchase_order(
        db, purchase_order_id, current_user.company_id, for_update=True
    )
    target = data.status
    if target not in PO_TRANSITIONS.get(order.status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Purchase Order-ის სტატუსის ცვლილება {order.status} → {target} დაუშვებელია",
        )

    manager_limit = await get_manager_approval_limit(db, current_user.company_id)
    approval_role = required_approval_role(order.total, manager_limit)
    if target == "approved":
        allowed = current_user.role == User.Role.ADMIN or (
            current_user.role == User.Role.MANAGER and approval_role == "manager"
        )
        if not allowed:
            detail = (
                "ამ თანხის Purchase Order-ის დამტკიცება მხოლოდ admin-ს შეუძლია"
                if approval_role == "admin"
                else "Purchase Order-ის დამტკიცება მხოლოდ manager-ს ან admin-ს შეუძლია"
            )
            raise HTTPException(status_code=403, detail=detail)

    previous = order.status
    order.status = target
    order.version += 1
    if target == "approved":
        order.approved_by = current_user.id
        order.approved_at = utc_now()
    db.add(
        PurchaseOrderStatusHistory(
            purchase_order_id=order.id,
            status=target,
            notes=data.notes,
            changed_by=current_user.id,
        )
    )
    await db.flush()
    add_audit(
        db,
        current_user,
        "purchase_order.status_changed",
        "purchase_order",
        order.id,
        {"from": previous, "to": target, "notes": data.notes},
    )
    order = await load_purchase_order(db, order.id, current_user.company_id)
    manager_limit = await get_manager_approval_limit(db, current_user.company_id)
    return ResponseBase(data=build_purchase_order_response(order, manager_limit))


@router.get(
    "/{purchase_order_id}/receipts",
    response_model=ResponseBase[list[GoodsReceiptResponse]],
)
async def list_goods_receipts(
    purchase_order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await load_purchase_order(db, purchase_order_id, current_user.company_id)
    receipts = (
        await db.execute(
            select(GoodsReceipt)
            .where(
                GoodsReceipt.purchase_order_id == purchase_order_id,
                GoodsReceipt.company_id == current_user.company_id,
            )
            .options(*RECEIPT_LOAD_OPTIONS)
            .order_by(GoodsReceipt.received_at)
        )
    ).unique().scalars().all()
    return ResponseBase(data=[build_receipt_response(receipt) for receipt in receipts])


@router.post(
    "/{purchase_order_id}/receipts",
    response_model=ResponseBase[GoodsReceiptResponse],
)
async def post_goods_receipt(
    purchase_order_id: UUID,
    data: GoodsReceiptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {User.Role.ADMIN, User.Role.MANAGER}:
        raise HTTPException(status_code=403, detail="საქონლის მიღების უფლება არ გაქვთ")

    idempotency_key = data.idempotency_key.strip()
    existing = await load_receipt_by_idempotency(
        db, current_user.company_id, idempotency_key
    )
    if existing:
        if existing.purchase_order_id != purchase_order_id:
            raise HTTPException(
                status_code=409,
                detail="idempotency key სხვა Purchase Order-ზე უკვე გამოყენებულია",
            )
        return ResponseBase(data=build_receipt_response(existing))

    order = await load_purchase_order(
        db, purchase_order_id, current_user.company_id, for_update=True
    )
    existing = await load_receipt_by_idempotency(
        db, current_user.company_id, idempotency_key
    )
    if existing:
        if existing.purchase_order_id != purchase_order_id:
            raise HTTPException(
                status_code=409,
                detail="idempotency key სხვა Purchase Order-ზე უკვე გამოყენებულია",
            )
        return ResponseBase(data=build_receipt_response(existing))

    if order.status not in {"approved", "partially_received"}:
        raise HTTPException(
            status_code=409,
            detail="საქონლის მიღება მხოლოდ approved ან partially_received Purchase Order-ზე შეიძლება",
        )

    requested_ids = [item.purchase_order_item_id for item in data.items]
    locked_items = (
        await db.execute(
            select(PurchaseOrderItem)
            .where(
                PurchaseOrderItem.id.in_(requested_ids),
                PurchaseOrderItem.purchase_order_id == order.id,
            )
            .with_for_update()
        )
    ).scalars().all()
    if len(locked_items) != len(requested_ids):
        raise HTTPException(status_code=404, detail="ერთი ან მეტი Purchase Order item არ მოიძებნა")
    locked_item_map = {item.id: item for item in locked_items}

    for request_item in data.items:
        order_item = locked_item_map[request_item.purchase_order_item_id]
        remaining = order_item.quantity - order_item.received_quantity
        if request_item.quantity > remaining:
            raise HTTPException(
                status_code=409,
                detail=f"მიღებული რაოდენობა დარჩენილ {remaining} ერთეულს აჭარბებს",
            )

    receipt_number = await allocate_document_number(
        db, current_user.company_id, "goods_receipt", "GR"
    )
    receipt = GoodsReceipt(
        company_id=current_user.company_id,
        purchase_order_id=order.id,
        warehouse_id=order.warehouse_id,
        receipt_number=receipt_number,
        idempotency_key=idempotency_key,
        status="posted",
        received_by=current_user.id,
        notes=data.notes,
    )
    db.add(receipt)
    await db.flush()

    for request_item in sorted(data.items, key=lambda row: str(locked_item_map[row.purchase_order_item_id].product_id)):
        order_item = locked_item_map[request_item.purchase_order_item_id]
        quantity = request_item.quantity
        product = (
            await db.execute(
                select(Product)
                .where(
                    Product.id == order_item.product_id,
                    Product.company_id == current_user.company_id,
                    Product.is_active.is_(True),
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")

        balance = (
            await db.execute(
                select(InventoryBalance)
                .where(
                    InventoryBalance.company_id == current_user.company_id,
                    InventoryBalance.warehouse_id == order.warehouse_id,
                    InventoryBalance.product_id == product.id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if balance is None:
            balance = InventoryBalance(
                company_id=current_user.company_id,
                warehouse_id=order.warehouse_id,
                product_id=product.id,
                quantity=Decimal("0"),
            )
            db.add(balance)
            await db.flush()

        previous_stock = Decimal(str(product.current_stock or 0))
        unit_cost = cost(
            Decimal(order_item.unit_price)
            * (Decimal("1") - Decimal(order_item.discount_percent) / Decimal("100"))
        )
        previous_average = (
            cost(Decimal(str(product.purchase_price or 0)))
            if previous_stock > 0
            else unit_cost
        )
        new_stock = previous_stock + quantity
        new_average = cost(
            (
                previous_stock * previous_average
                + quantity * unit_cost
            ) / new_stock
        )

        balance.quantity = Decimal(balance.quantity) + quantity
        product.current_stock = float(new_stock)
        product.purchase_price = float(new_average)
        order_item.received_quantity = Decimal(order_item.received_quantity) + quantity
        receipt_item = GoodsReceiptItem(
            goods_receipt_id=receipt.id,
            purchase_order_item_id=order_item.id,
            product_id=product.id,
            quantity=quantity,
        )
        db.add(receipt_item)
        await db.flush()
        db.add(
            PurchaseCostHistory(
                company_id=current_user.company_id,
                supplier_id=order.supplier_id,
                purchase_order_id=order.id,
                goods_receipt_id=receipt.id,
                goods_receipt_item_id=receipt_item.id,
                product_id=product.id,
                quantity=quantity,
                unit_cost=unit_cost,
                previous_stock=previous_stock,
                new_stock=new_stock,
                previous_average_cost=previous_average,
                new_average_cost=new_average,
            )
        )
        db.add(
            InventoryMovement(
                company_id=current_user.company_id,
                warehouse_id=order.warehouse_id,
                product_id=product.id,
                movement_type="purchase_receipt",
                quantity=quantity,
                balance_after=balance.quantity,
                reason="purchase_order_receipt",
                notes=data.notes,
                reference=receipt_number,
                created_by=current_user.id,
            )
        )

    all_items = (
        await db.execute(
            select(PurchaseOrderItem).where(
                PurchaseOrderItem.purchase_order_id == order.id
            )
        )
    ).scalars().all()
    next_status = (
        "received"
        if all(item.received_quantity >= item.quantity for item in all_items)
        else "partially_received"
    )
    previous_status = order.status
    if next_status != previous_status:
        order.status = next_status
        db.add(
            PurchaseOrderStatusHistory(
                purchase_order_id=order.id,
                status=next_status,
                notes=f"Goods Receipt: {receipt_number}",
                changed_by=current_user.id,
            )
        )

    await db.flush()
    add_audit(
        db,
        current_user,
        "goods_receipt.posted",
        "goods_receipt",
        receipt.id,
        {
            "receipt_number": receipt_number,
            "purchase_order_id": order.id,
            "purchase_order_status": next_status,
            "items": [
                {
                    "purchase_order_item_id": item.purchase_order_item_id,
                    "quantity": item.quantity,
                }
                for item in data.items
            ],
        },
    )
    # GL: Dr 1200 (inventory) / Cr 2110 (goods in transit) — Odoo-style receipt posting
    from app.services.gl_hooks import post_goods_receipt_gl
    receipt_subtotal = sum(
        (Decimal(locked_item_map[item.purchase_order_item_id].unit_price)
         * Decimal(item.quantity))
        for item in data.items
    )
    await post_goods_receipt_gl(
        db, current_user.company_id, current_user,
        receipt_id=receipt.id,
        receipt_number=receipt_number,
        receipt_date=date.today(),
        subtotal=receipt_subtotal,
    )
    receipt = (
        await db.execute(
            select(GoodsReceipt)
            .where(GoodsReceipt.id == receipt.id)
            .options(*RECEIPT_LOAD_OPTIONS)
        )
    ).unique().scalar_one()
    return ResponseBase(data=build_receipt_response(receipt))


# ── Quality check ───────────────────────────────────────────────────


@router.post(
    "/{purchase_order_id}/receipts/{receipt_id}/quality-check",
    response_model=ResponseBase[dict],
)
async def quality_check_receipt(
    purchase_order_id: UUID,
    receipt_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record the quality check result for a goods receipt (P1.9)."""
    receipt = (
        await db.execute(
            select(GoodsReceipt).where(
                GoodsReceipt.id == receipt_id,
                GoodsReceipt.purchase_order_id == purchase_order_id,
                GoodsReceipt.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="მიღება არ მოიძებნა")
    status = data.get("status", "passed")
    if status not in ("pending", "passed", "failed", "partial"):
        raise HTTPException(status_code=422, detail="არასწორი ხარისხის სტატუსი")
    receipt.quality_status = status
    receipt.quality_notes = data.get("notes")
    receipt.quality_checked_by = current_user.id
    receipt.quality_checked_at = datetime.utcnow()
    await db.flush()
    return ResponseBase(data={
        "receipt_id": str(receipt.id),
        "quality_status": receipt.quality_status,
        "quality_notes": receipt.quality_notes,
    }, message="ხარისხის შემოწმება შენახულია")


# ── Three-Way Matching ──────────────────────────────────────────────


@router.get(
    "/{purchase_order_id}/three-way-match",
    response_model=ResponseBase[ThreeWayMatchSummary],
)
async def get_three_way_match(
    purchase_order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare ordered vs received vs billed quantities and amounts."""
    order = await load_purchase_order(db, purchase_order_id, current_user.company_id)

    # Load supplier invoices for this PO to get billed quantities
    from app.models.purchase import SupplierInvoice, SupplierInvoiceItem

    invoices = (
        await db.execute(
            select(SupplierInvoice)
            .where(
                SupplierInvoice.purchase_order_id == purchase_order_id,
                SupplierInvoice.company_id == current_user.company_id,
            )
            .options(selectinload(SupplierInvoice.items))
        )
    ).unique().scalars().all()

    # Build billed quantity map per PO item
    billed_qty_map: dict[UUID, Decimal] = {}
    billed_amt_map: dict[UUID, Decimal] = {}
    for inv in invoices:
        for inv_item in inv.items:
            po_item_id = inv_item.purchase_order_item_id
            billed_qty_map[po_item_id] = (
                billed_qty_map.get(po_item_id, Decimal("0")) + inv_item.quantity
            )
            billed_amt_map[po_item_id] = (
                billed_amt_map.get(po_item_id, Decimal("0")) + inv_item.line_total
            )

    total_ordered = Decimal("0")
    total_received = Decimal("0")
    total_billed = Decimal("0")
    total_ordered_amount = Decimal("0")
    total_billed_amount = Decimal("0")
    match_items = []
    all_match = True

    for item in order.items:
        ordered_qty = item.quantity
        received_qty = item.received_quantity
        billed_qty = billed_qty_map.get(item.id, Decimal("0"))
        ordered_amt = item.line_total
        billed_amt = billed_amt_map.get(item.id, Decimal("0"))

        total_ordered += ordered_qty
        total_received += received_qty
        total_billed += billed_qty
        total_ordered_amount += ordered_amt
        total_billed_amount += billed_amt

        # Determine quantity match
        if received_qty < ordered_qty:
            qty_match = "under_received"
            all_match = False
        elif received_qty > ordered_qty:
            qty_match = "over_received"
            all_match = False
        elif billed_qty < ordered_qty:
            qty_match = "under_billed"
            all_match = False
        elif billed_qty > ordered_qty:
            qty_match = "over_billed"
            all_match = False
        else:
            qty_match = "ok"

        # Price match: compare unit_price from PO item vs invoice item
        price_match = "ok"
        if billed_qty > 0 and billed_amt > 0:
            avg_billed_price = billed_amt / billed_qty
            po_unit_price = item.unit_price * (
                Decimal("1") - item.discount_percent / Decimal("100")
            )
            if abs(avg_billed_price - po_unit_price) > Decimal("0.01"):
                price_match = "price_mismatch"
                all_match = False

        overall = "match" if qty_match == "ok" and price_match == "ok" else "mismatch"

        match_items.append({
            "purchase_order_item_id": item.id,
            "product_name": item.product_name,
            "ordered_quantity": float(ordered_qty),
            "received_quantity": float(received_qty),
            "billed_quantity": float(billed_qty),
            "ordered_amount": float(ordered_amt),
            "billed_amount": float(billed_amt),
            "quantity_match": qty_match,
            "price_match": price_match,
            "overall": overall,
        })

    if all_match:
        match_status = "full_match"
    elif total_billed == Decimal("0") and total_received == Decimal("0"):
        match_status = "partial_match"
    else:
        match_status = "mismatch"

    return ResponseBase(
        data=ThreeWayMatchSummary(
            purchase_order_id=order.id,
            purchase_order_number=order.purchase_order_number,
            supplier_name=order.supplier.name,
            total_ordered=float(total_ordered),
            total_received=float(total_received),
            total_billed=float(total_billed),
            total_ordered_amount=float(total_ordered_amount),
            total_billed_amount=float(total_billed_amount),
            match_status=match_status,
            items=match_items,
        )
    )


# ── Workflow Tracking ────────────────────────────────────────────────


@router.get(
    "/{purchase_order_id}/workflow",
    response_model=ResponseBase[PurchaseWorkflowResponse],
)
async def get_purchase_workflow(
    purchase_order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Visual workflow: PO → Goods Receipt → Supplier Invoice."""
    order = await load_purchase_order(db, purchase_order_id, current_user.company_id)

    # Load receipts
    receipts = (
        await db.execute(
            select(GoodsReceipt)
            .where(
                GoodsReceipt.purchase_order_id == purchase_order_id,
                GoodsReceipt.company_id == current_user.company_id,
            )
            .order_by(GoodsReceipt.received_at)
        )
    ).scalars().all()

    # Load supplier invoices
    from app.models.purchase import SupplierInvoice

    invoices = (
        await db.execute(
            select(SupplierInvoice)
            .where(
                SupplierInvoice.purchase_order_id == purchase_order_id,
                SupplierInvoice.company_id == current_user.company_id,
            )
            .order_by(SupplierInvoice.created_at)
        )
    ).scalars().all()

    status = order.status
    steps = []

    # Step 1: PO Created
    po_created = any(
        h.status == "draft" for h in order.status_history
    ) if order.status_history else True
    steps.append({
        "step": "po_created",
        "label": "Purchase Order",
        "status": "completed" if po_created else "active",
        "timestamp": order.created_at,
        "reference": order.purchase_order_number,
        "reference_id": order.id,
    })

    # Step 2: PO Approved
    approved = order.status in {"approved", "partially_received", "received"}
    steps.append({
        "step": "po_approved",
        "label": "დამტკიცება",
        "status": "completed" if approved else ("active" if status == "draft" else "skipped"),
        "timestamp": order.approved_at,
        "reference": order.purchase_order_number,
        "reference_id": order.id,
    })

    # Step 3: Goods Receipt
    has_receipts = len(receipts) > 0
    all_received = status in {"received", "partially_received"}
    steps.append({
        "step": "goods_receipt",
        "label": "საქონლის მიღება",
        "status": "completed" if all_received and has_receipts else (
            "active" if approved and not all_received else (
                "completed" if has_receipts else "pending"
            )
        ),
        "timestamp": receipts[-1].received_at if receipts else None,
        "reference": receipts[-1].receipt_number if receipts else None,
        "reference_id": receipts[-1].id if receipts else None,
    })

    # Step 4: Supplier Invoice
    has_invoices = len(invoices) > 0
    steps.append({
        "step": "supplier_invoice",
        "label": "მომწოდებლის ინვოისი",
        "status": "completed" if has_invoices else (
            "active" if all_received else "pending"
        ),
        "timestamp": invoices[-1].created_at if invoices else None,
        "reference": invoices[-1].internal_invoice_number if invoices else None,
        "reference_id": invoices[-1].id if invoices else None,
    })

    # Step 5: Paid
    from app.models.purchase import SupplierPayable

    is_paid = False
    if invoices:
        invoice_ids = [inv.id for inv in invoices]
        payable = (
            await db.execute(
                select(SupplierPayable).where(
                    SupplierPayable.supplier_invoice_id.in_(invoice_ids)
                )
            )
        ).scalars().all()
        is_paid = any(p.status == "paid" for p in payable)
    steps.append({
        "step": "paid",
        "label": "გადახდილი",
        "status": "completed" if is_paid else (
            "active" if has_invoices else "pending"
        ),
        "timestamp": None,
        "reference": None,
        "reference_id": None,
    })

    return ResponseBase(
        data=PurchaseWorkflowResponse(
            purchase_order_id=order.id,
            purchase_order_number=order.purchase_order_number,
            supplier_name=order.supplier.name,
            total=float(order.total),
            status=status,
            steps=steps,
        )
    )


# ── Approval Limit Visualization ────────────────────────────────────


@router.get(
    "/approval-limits",
    response_model=ResponseBase[ApprovalLimitInfo],
)
async def get_approval_limit_info(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Show approval limit vs current PO totals for visualization."""
    manager_limit = await get_manager_approval_limit(db, current_user.company_id)

    # Get all non-cancelled POs
    pos = (
        await db.execute(
            select(PurchaseOrder.total).where(
                PurchaseOrder.company_id == current_user.company_id,
                PurchaseOrder.status != "cancelled",
            )
        )
    ).scalars().all()

    total_count = len(pos)
    within_limit = sum(1 for t in pos if Decimal(str(t)) <= manager_limit)
    exceeding = total_count - within_limit

    # Current PO total (sum of all non-cancelled)
    current_total = sum(Decimal(str(t)) for t in pos) if pos else Decimal("0")

    return ResponseBase(
        data=ApprovalLimitInfo(
            manager_approval_limit=float(manager_limit),
            current_po_total=float(current_total),
            requires_admin=current_total > manager_limit,
            po_count_within_limit=within_limit,
            po_count_exceeding_limit=exceeding,
            po_count_total=total_count,
        )
    )


# ---------- PO 2.0 ----------


@router.post(
    "/{purchase_order_id}/create-supplier-invoice",
    response_model=ResponseBase,
)
async def create_supplier_invoice_from_po(
    purchase_order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """One-click supplier invoice from a PO — uses billed quantities/PO prices."""
    import uuid as _uuid

    po = (
        await db.execute(
            select(PurchaseOrder)
            .where(
                PurchaseOrder.id == purchase_order_id,
                PurchaseOrder.company_id == current_user.company_id,
            )
            .options(selectinload(PurchaseOrder.items))
        )
    ).scalars().first()
    if not po:
        raise HTTPException(status_code=404, detail="PO არ მოიძებნა")
    if po.status not in ("approved", "received", "partially_received"):
        raise HTTPException(status_code=400, detail="PO-დან ინვოისი მხოლოდ approved/received სტატუსზე იქმნება")

    # supplier invoice already exists for this PO?
    existing = (
        await db.execute(
            select(SupplierInvoice).where(
                SupplierInvoice.purchase_order_id == po.id,
                SupplierInvoice.company_id == current_user.company_id,
            )
        )
    ).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="ამ PO-სთვის ინვოისი უკვე შექმნილია")

    # allocate invoice number via canonical sequence helper
    inv_number = await allocate_document_number(db, current_user.company_id, "supplier_invoice", "SINV")

    subtotal = Decimal("0")
    vat_total = Decimal("0")
    inv_items = []
    for po_item in po.items:
        qty = po_item.quantity  # bill full ordered qty (or received if partial)
        price = po_item.unit_price
        line_sub = (qty * price).quantize(Decimal("0.01"))
        line_vat = (line_sub * po_item.vat_rate / Decimal("100")).quantize(Decimal("0.01"))
        subtotal += line_sub
        vat_total += line_vat
        inv_items.append(
            SupplierInvoiceItem(
                id=_uuid.uuid4(),
                supplier_invoice_id=None,  # set below
                purchase_order_item_id=po_item.id,
                product_id=po_item.product_id,
                product_name=po_item.product_name,
                quantity=qty,
                unit_price=price,
                discount_percent=po_item.discount_percent,
                vat_rate=po_item.vat_rate,
                line_subtotal=line_sub,
                vat_amount=line_vat,
                line_total=line_sub + line_vat,
                matching_status="unmatched",
                match_issue=None,
            )
        )

    inv = SupplierInvoice(
        id=_uuid.uuid4(),
        company_id=current_user.company_id,
        supplier_id=po.supplier_id,
        purchase_order_id=po.id,
        fiscal_position_id=po.fiscal_position_id,
        tax_account_code=None,
        internal_invoice_number=inv_number,
        supplier_invoice_number=inv_number,
        invoice_date=date.today(),
        due_date=date.today(),
        status="draft",
        matching_status="unmatched",
        match_issues="[]",
        subtotal=subtotal,
        vat_amount=vat_total,
        total=subtotal + vat_total,
        notes=f"ავტომატურად PO-დან: {po.purchase_order_number}",
        created_by=current_user.id,
    )
    db.add(inv)
    await db.flush()
    for it in inv_items:
        it.supplier_invoice_id = inv.id
        db.add(it)

    # record history
    db.add(
        PurchaseOrderStatusHistory(
            id=_uuid.uuid4(),
            purchase_order_id=po.id,
            status=po.status,
            notes=f"Supplier invoice {inv_number} ავტომატურად შექმნილი",
            changed_by=current_user.id,
        )
    )
    await db.commit()

    return ResponseBase(
        data={
            "supplier_invoice_id": str(inv.id),
            "supplier_invoice_number": inv_number,
            "total": float(inv.total),
            "status": "draft",
        },
        message="Supplier invoice წარმატებით შექმნილია PO-დან",
    )


@router.post(
    "/{purchase_order_id}/scheduled-deliveries",
    response_model=ResponseBase,
)
async def create_scheduled_delivery(
    purchase_order_id: UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a scheduled delivery (date + qty) to an approved PO."""
    import uuid as _uuid

    po = (
        await db.execute(
            select(PurchaseOrder).where(
                PurchaseOrder.id == purchase_order_id,
                PurchaseOrder.company_id == current_user.company_id,
            )
        )
    ).scalars().first()
    if not po:
        raise HTTPException(status_code=404, detail="PO არ მოიძებნა")

    sched_date = payload.get("scheduled_date")
    qty = payload.get("quantity")
    if not sched_date or not qty:
        raise HTTPException(status_code=400, detail="scheduled_date და quantity სავალდებულოა")

    sd = ScheduledDelivery(
        id=_uuid.uuid4(),
        company_id=current_user.company_id,
        purchase_order_id=po.id,
        scheduled_date=date.fromisoformat(sched_date),
        quantity=Decimal(str(qty)),
        status=payload.get("status", "planned"),
        note=payload.get("note"),
    )
    db.add(sd)
    await db.commit()
    return ResponseBase(
        data={
            "scheduled_delivery_id": str(sd.id),
            "scheduled_date": sched_date,
            "quantity": float(sd.quantity),
            "status": sd.status,
        },
        message="Scheduled delivery დამატებულია",
    )


@router.get(
    "/{purchase_order_id}/scheduled-deliveries",
    response_model=ResponseBase,
)
async def list_scheduled_deliveries(
    purchase_order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all scheduled deliveries for a PO."""
    rows = (
        await db.execute(
            select(ScheduledDelivery)
            .where(
                ScheduledDelivery.purchase_order_id == purchase_order_id,
                ScheduledDelivery.company_id == current_user.company_id,
            )
            .order_by(ScheduledDelivery.scheduled_date)
        )
    ).scalars().all()
    return ResponseBase(
        data=[
            {
                "id": str(r.id),
                "scheduled_date": r.scheduled_date.isoformat(),
                "quantity": float(r.quantity),
                "status": r.status,
                "note": r.note,
            }
            for r in rows
        ],
        message="Scheduled deliveries",
    )


@router.get(
    "/{purchase_order_id}/backorder",
    response_model=ResponseBase,
)
async def get_backorder(
    purchase_order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Backorder: quantities still owed = ordered - received, per item."""
    items = (
        await db.execute(
            select(PurchaseOrderItem).where(
                PurchaseOrderItem.purchase_order_id == purchase_order_id,
            )
        )
    ).scalars().all()

    rows = []
    for it in items:
        owed = it.quantity - it.received_quantity
        if owed > 0:
            rows.append(
                {
                    "purchase_order_item_id": str(it.id),
                    "product_id": str(it.product_id),
                    "product_name": it.product_name,
                    "ordered_quantity": float(it.quantity),
                    "received_quantity": float(it.received_quantity),
                    "backorder_quantity": float(owed),
                    "expected_date": None,
                }
            )
    # include persisted backorder records if any
    persisted = (
        await db.execute(
            select(PurchaseOrderBackorder).where(
                PurchaseOrderBackorder.purchase_order_id == purchase_order_id,
            )
        )
    ).scalars().all()
    for b in persisted:
        if b.status == "open":
            rows.append(
                {
                    "purchase_order_item_id": str(b.purchase_order_item_id),
                    "product_id": str(b.product_id),
                    "product_name": "—",
                    "ordered_quantity": float(b.quantity),
                    "received_quantity": float(b.fulfilled_quantity),
                    "backorder_quantity": float(b.quantity - b.fulfilled_quantity),
                    "expected_date": b.expected_date.isoformat() if b.expected_date else None,
                    "backorder_id": str(b.id),
                }
            )
    return ResponseBase(data=rows, message="Backorder ინფორმაცია")


@router.get(
    "/{purchase_order_id}/returns",
    response_model=ResponseBase,
)
async def list_purchase_returns(
    purchase_order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List purchase returns for a PO."""
    rows = (
        await db.execute(
            select(PurchaseReturn)
            .where(
                PurchaseReturn.purchase_order_id == purchase_order_id,
                PurchaseReturn.company_id == current_user.company_id,
            )
            .order_by(PurchaseReturn.created_at.desc())
        )
    ).scalars().all()
    return ResponseBase(
        data=[
            {
                "id": str(r.id),
                "return_number": r.return_number,
                "status": r.status,
                "return_date": r.return_date.isoformat() if r.return_date else None,
                "reason": r.reason,
                "total": float(r.total),
                "restock_warehouse": r.restock_warehouse,
            }
            for r in rows
        ],
        message="Purchase returns",
    )


@router.post(
    "/{purchase_order_id}/returns",
    response_model=ResponseBase,
)
async def create_purchase_return(
    purchase_order_id: UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a purchase return (RMA) with items and reason."""
    import uuid as _uuid

    po = (
        await db.execute(
            select(PurchaseOrder).where(
                PurchaseOrder.id == purchase_order_id,
                PurchaseOrder.company_id == current_user.company_id,
            )
        )
    ).scalars().first()
    if not po:
        raise HTTPException(status_code=404, detail="PO არ მოიძებნა")

    items_data = payload.get("items", [])
    if not items_data:
        raise HTTPException(status_code=400, detail="დასაბრუნებელი ნივთები აუცილებელია")

    ret_number = await allocate_document_number(db, current_user.company_id, "purchase_return", "RET")

    total = Decimal("0")
    ret_items = []
    for it in items_data:
        po_item = (
            await db.execute(
                select(PurchaseOrderItem).where(
                    PurchaseOrderItem.id == it["purchase_order_item_id"],
                    PurchaseOrderItem.purchase_order_id == po.id,
                )
            )
        ).scalars().first()
        if not po_item:
            raise HTTPException(status_code=404, detail="PO item არ მოიძებნა")
        qty = Decimal(str(it["quantity"]))
        if qty > po_item.received_quantity:
            raise HTTPException(status_code=400, detail="დასაბრუნებელი რაოდენობა აღემატება მიღებულს")
        price = po_item.unit_price
        line_total = (qty * price).quantize(Decimal("0.01"))
        total += line_total
        ret_items.append(
            PurchaseReturnItem(
                id=_uuid.uuid4(),
                purchase_order_item_id=po_item.id,
                product_id=po_item.product_id,
                product_name=po_item.product_name,
                quantity=qty,
                unit_price=price,
                line_total=line_total,
                reason=it.get("reason"),
            )
        )

    ret = PurchaseReturn(
        id=_uuid.uuid4(),
        company_id=current_user.company_id,
        purchase_order_id=po.id,
        supplier_id=po.supplier_id,
        return_number=ret_number,
        status="draft",
        return_date=date.fromisoformat(payload["return_date"]) if payload.get("return_date") else None,
        reason=payload.get("reason"),
        total=total,
        restock_warehouse=payload.get("restock_warehouse", True),
        notes=payload.get("notes"),
        created_by=current_user.id,
    )
    db.add(ret)
    await db.flush()
    for ri in ret_items:
        ri.purchase_return_id = ret.id
        db.add(ri)

    # stock back
    if payload.get("restock_warehouse", True):
        for ri in ret_items:
            # reduce received qty on PO item
            po_item = (
                await db.execute(
                    select(PurchaseOrderItem).where(PurchaseOrderItem.id == ri.purchase_order_item_id)
                )
            ).scalars().first()
            if po_item:
                po_item.received_quantity = max(Decimal("0"), po_item.received_quantity - ri.quantity)
    await db.commit()

    return ResponseBase(
        data={
            "return_id": str(ret.id),
            "return_number": ret_number,
            "status": "draft",
            "total": float(total),
            "item_count": len(ret_items),
        },
        message="Purchase return შექმნილია",
    )


@router.post(
    "/{purchase_order_id}/amendments",
    response_model=ResponseBase,
)
async def create_po_amendment(
    purchase_order_id: UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Propose an amendment (version bump) to an approved PO; pending until approved."""
    import uuid as _uuid

    po = (
        await db.execute(
            select(PurchaseOrder).where(
                PurchaseOrder.id == purchase_order_id,
                PurchaseOrder.company_id == current_user.company_id,
            )
        )
    ).scalars().first()
    if not po:
        raise HTTPException(status_code=404, detail="PO არ მოიძებნა")

    changes = payload.get("changes", {})
    if not changes:
        raise HTTPException(status_code=400, detail="changes ველი აუცილებელია (JSON)")

    version = po.version + 1
    amend = PurchaseOrderAmendment(
        id=_uuid.uuid4(),
        company_id=current_user.company_id,
        purchase_order_id=po.id,
        version=version,
        status="pending",
        changes=json.dumps(changes, ensure_ascii=False, default=str),
        proposed_by=current_user.id,
        note=payload.get("note"),
    )
    db.add(amend)
    await db.commit()
    return ResponseBase(
        data={
            "amendment_id": str(amend.id),
            "version": version,
            "status": "pending",
        },
        message="Amendment წარდგენილია დასამტკიცებლად",
    )


@router.post(
    "/amendments/{amendment_id}/approve",
    response_model=ResponseBase,
)
async def approve_po_amendment(
    amendment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve a pending PO amendment — applies changes and bumps PO version."""
    import uuid as _uuid

    amend = (
        await db.execute(
            select(PurchaseOrderAmendment).where(
                PurchaseOrderAmendment.id == amendment_id,
                PurchaseOrderAmendment.company_id == current_user.company_id,
            )
        )
    ).scalars().first()
    if not amend:
        raise HTTPException(status_code=404, detail="Amendment არ მოიძებნა")
    if amend.status != "pending":
        raise HTTPException(status_code=409, detail="Amendment უკვე დამუშავებულია")

    po = (
        await db.execute(
            select(PurchaseOrder).where(PurchaseOrder.id == amend.purchase_order_id)
        )
    ).scalars().first()
    if not po:
        raise HTTPException(status_code=404, detail="PO არ მოიძებნა")

    # apply changes
    try:
        ch = json.loads(amend.changes)
    except Exception:
        ch = {}
    if "expected_delivery_date" in ch:
        po.expected_delivery_date = date.fromisoformat(str(ch["expected_delivery_date"]))
    if "notes" in ch:
        po.notes = str(ch["notes"])
    # item price/qty adjustments
    item_changes = ch.get("items", [])
    for ic in item_changes:
        if "purchase_order_item_id" not in ic:
            continue
        po_item = (
            await db.execute(
                select(PurchaseOrderItem).where(
                    PurchaseOrderItem.id == ic["purchase_order_item_id"],
                    PurchaseOrderItem.purchase_order_id == po.id,
                )
            )
        ).scalars().first()
        if not po_item:
            continue
        if "quantity" in ic:
            po_item.quantity = Decimal(str(ic["quantity"]))
        if "unit_price" in ic:
            po_item.unit_price = Decimal(str(ic["unit_price"]))
            po_item.line_subtotal = (po_item.quantity * po_item.unit_price).quantize(Decimal("0.01"))
            po_item.vat_amount = (po_item.line_subtotal * po_item.vat_rate / Decimal("100")).quantize(Decimal("0.01"))
            po_item.line_total = po_item.line_subtotal + po_item.vat_amount

    po.version = amend.version
    amend.status = "approved"
    amend.approved_by = current_user.id
    amend.approved_at = utc_now()
    db.add(
        PurchaseOrderStatusHistory(
            id=_uuid.uuid4(),
            purchase_order_id=po.id,
            status=po.status,
            notes=f"Amendment v{amend.version} დამტკიცდა",
            changed_by=current_user.id,
        )
    )
    await db.commit()
    return ResponseBase(
        data={
            "amendment_id": str(amend.id),
            "po_version": po.version,
            "status": "approved",
        },
        message="Amendment დამტკიცებულია, PO ვერსია განახლდა",
    )


@router.get(
    "/{purchase_order_id}/amendments",
    response_model=ResponseBase,
)
async def list_po_amendments(
    purchase_order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List amendments for a PO."""
    rows = (
        await db.execute(
            select(PurchaseOrderAmendment)
            .where(
                PurchaseOrderAmendment.purchase_order_id == purchase_order_id,
                PurchaseOrderAmendment.company_id == current_user.company_id,
            )
            .order_by(PurchaseOrderAmendment.version.desc())
        )
    ).scalars().all()
    return ResponseBase(
        data=[
            {
                "id": str(r.id),
                "version": r.version,
                "status": r.status,
                "proposed_by": str(r.proposed_by) if r.proposed_by else None,
                "approved_by": str(r.approved_by) if r.approved_by else None,
                "note": r.note,
                "changes": json.loads(r.changes) if r.changes else {},
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "approved_at": r.approved_at.isoformat() if r.approved_at else None,
            }
            for r in rows
        ],
        message="PO amendments",
    )


@router.get(
    "/{purchase_order_id}/landed-costs",
    response_model=ResponseBase,
)
async def list_po_landed_costs(
    purchase_order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Landed costs linked to this PO (WMS module)."""
    from app.models.wms_ops import LandedCost

    rows = (
        await db.execute(
            select(LandedCost)
            .where(
                LandedCost.purchase_order_id == purchase_order_id,
                LandedCost.company_id == current_user.company_id,
            )
            .order_by(LandedCost.created_at.desc())
        )
    ).scalars().all()
    return ResponseBase(
        data=[
            {
                "id": str(r.id),
                "description": r.description,
                "total_amount": float(r.total_amount),
                "currency": r.currency,
                "allocated": r.allocated,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        message="Landed costs",
    )


@router.post(
    "/{purchase_order_id}/validate-prices",
    response_model=ResponseBase,
)
async def validate_po_prices_against_supplier_list(
    purchase_order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Supplier pricelist validation: compare PO unit prices vs supplier_price_lists."""
    po = (
        await db.execute(
            select(PurchaseOrder).where(
                PurchaseOrder.id == purchase_order_id,
                PurchaseOrder.company_id == current_user.company_id,
            )
        )
    ).scalars().first()
    if not po:
        raise HTTPException(status_code=404, detail="PO არ მოიძებნა")

    items = (
        await db.execute(
            select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == po.id)
        )
    ).scalars().all()
    from app.models.procurement import SupplierPriceList as SPL

    results = []
    for it in items:
        spl = (
            await db.execute(
                select(SPL)
                .where(
                    SPL.supplier_id == po.supplier_id,
                    SPL.product_id == it.product_id,
                    SPL.company_id == current_user.company_id,
                )
                .order_by(SPL.priority.asc())
            )
        ).scalars().first()
        po_price = it.unit_price
        list_price = spl.price if spl else None
        status = "ok"
        note = None
        if list_price is None:
            status = "no_list"
            note = "მომწოდებლის ფასთა სიაში არ არის"
        elif list_price < po_price:
            status = "above_list"
            note = f"PO ფასი ({po_price}) აღემატება სიის ფასს ({list_price})"
        results.append(
            {
                "purchase_order_item_id": str(it.id),
                "product_id": str(it.product_id),
                "product_name": it.product_name,
                "po_unit_price": float(po_price),
                "supplier_list_price": float(list_price) if list_price is not None else None,
                "status": status,
                "note": note,
            }
        )
    return ResponseBase(data=results, message="Supplier pricelist validation")
