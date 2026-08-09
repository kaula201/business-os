"""Global search across core modules (clients, products, orders, suppliers)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.client import Client
from app.models.invoice import Invoice
from app.models.order import Order
from app.models.product import Product
from app.models.purchase import Supplier
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/search", tags=["ძებნა"])

MAX_RESULTS = 5


@router.get("", response_model=ResponseBase[dict])
async def global_search(
    q: str = Query(..., min_length=1, max_length=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search clients, products, orders, invoices and suppliers by name/number."""
    term = f"%{q.strip()}%"
    company_id = current_user.company_id

    clients = (
        await db.execute(
            select(Client.id, Client.name, Client.identification_code, Client.status)
            .where(
                Client.company_id == company_id,
                or_(Client.name.ilike(term), Client.identification_code.ilike(term)),
            )
            .limit(MAX_RESULTS)
        )
    ).all()

    products = (
        await db.execute(
            select(Product.id, Product.name, Product.sku)
            .where(Product.company_id == company_id, or_(Product.name.ilike(term), Product.sku.ilike(term)))
            .limit(MAX_RESULTS)
        )
    ).all()

    orders = (
        await db.execute(
            select(Order.id, Order.order_number, Client.name.label("client_name"))
            .join(Client, Client.id == Order.client_id)
            .where(Order.company_id == company_id, Order.order_number.ilike(term))
            .limit(MAX_RESULTS)
        )
    ).all()

    invoices = (
        await db.execute(
            select(Invoice.id, Invoice.invoice_number, Client.name.label("client_name"))
            .join(Client, Client.id == Invoice.client_id)
            .where(Invoice.company_id == company_id, Invoice.invoice_number.ilike(term))
            .limit(MAX_RESULTS)
        )
    ).all()

    suppliers = (
        await db.execute(
            select(Supplier.id, Supplier.name, Supplier.identification_code)
            .where(Supplier.company_id == company_id, Supplier.name.ilike(term))
            .limit(MAX_RESULTS)
        )
    ).all()

    return ResponseBase(data={
        "clients": [{"id": str(c.id), "name": c.name, "identification_code": c.identification_code, "status": c.status} for c in clients],
        "products": [{"id": str(p.id), "name": p.name, "sku": p.sku} for p in products],
        "orders": [{"id": str(o.id), "order_number": o.order_number, "client_name": o.client_name} for o in orders],
        "invoices": [{"id": str(i.id), "invoice_number": i.invoice_number, "client_name": i.client_name} for i in invoices],
        "suppliers": [{"id": str(s.id), "name": s.name, "identification_code": s.identification_code} for s in suppliers],
    })
