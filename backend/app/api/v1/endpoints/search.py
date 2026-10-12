"""Global search across core modules (clients, products, orders, suppliers)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.modules import is_module_enabled
from app.models.client import Client
from app.models.invoice import Invoice
from app.models.order import Order
from app.models.product import Product
from app.models.purchase import Supplier
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/search", tags=["ძებნა"])

MAX_RESULTS = 5

# Georgian ↔ Latin transliteration maps (standard Georgian National System)
_GEO_TO_LATIN = {
    "ა": "a", "ბ": "b", "გ": "g", "დ": "d", "ე": "e", "ვ": "v", "ზ": "z",
    "თ": "t", "ი": "i", "კ": "k", "ლ": "l", "მ": "m", "ნ": "n", "ო": "o",
    "პ": "p", "ჟ": "zh", "რ": "r", "ს": "s", "ტ": "t", "უ": "u", "ფ": "p",
    "ქ": "k", "ღ": "gh", "ყ": "q", "შ": "sh", "ჩ": "ch", "ც": "ts", "ძ": "dz",
    "წ": "ts", "ჭ": "ch", "ხ": "kh", "ჯ": "j", "ჰ": "h",
}
_LATIN_TO_GEO = {
    "a": "ა", "b": "ბ", "g": "გ", "d": "დ", "e": "ე", "v": "ვ", "z": "ზ",
    "t": "თ", "i": "ი", "k": "კ", "l": "ლ", "m": "მ", "n": "ნ", "o": "ო",
    "p": "პ", "r": "რ", "s": "ს", "u": "უ", "q": "ყ", "h": "ჰ", "j": "ჯ",
}
# Multi-char Latin digraphs must be replaced first
_LATIN_DIGRAPHS = {"sh": "შ", "ch": "ჩ", "ts": "ც", "dz": "ძ", "gh": "ღ", "kh": "ხ", "zh": "ჟ"}


def geo_to_latin(text: str) -> str:
    return "".join(_GEO_TO_LATIN.get(ch, ch) for ch in text)


def latin_to_geo(text: str) -> str:
    result = text
    for digraph, geo in _LATIN_DIGRAPHS.items():
        result = result.replace(digraph, geo)
    return "".join(_LATIN_TO_GEO.get(ch.lower(), ch) for ch in result)


def search_patterns(q: str) -> list[str]:
    """Build OR-search patterns: original, latin→geo, geo→latin."""
    q = q.strip()
    patterns = {f"%{q}%"}
    latinized = geo_to_latin(q)
    if latinized.lower() != q.lower():
        patterns.add(f"%{latinized}%")
    georgianized = latin_to_geo(q)
    if georgianized != q:
        patterns.add(f"%{georgianized}%")
    return list(patterns)


@router.get("", response_model=ResponseBase[dict])
async def global_search(
    q: str = Query(..., min_length=1, max_length=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search clients, products, orders, invoices and suppliers by name/number.

    Handles Georgian and Latin input: typing 'iveria' finds 'შპს ივერია' and
    vice versa via transliteration.

    Issue #52 / REQ-PKG: search must not leak data of modules the company
    has not bought. Sections are queried only when the company owns the
    corresponding module.
    """
    patterns = search_patterns(q)
    company_id = current_user.company_id

    clients_data = []
    if await is_module_enabled(db, company_id, "clients"):
        clients = (
            await db.execute(
                select(Client.id, Client.name, Client.identification_code, Client.status)
                .where(
                    Client.company_id == company_id,
                    or_(
                        *(Client.name.ilike(p) for p in patterns),
                        *(Client.identification_code.ilike(p) for p in patterns),
                    ),
                )
                .limit(MAX_RESULTS)
            )
        ).all()
        clients_data = [
            {"id": str(c.id), "name": c.name, "identification_code": c.identification_code, "status": c.status}
            for c in clients
        ]

    products_data = []
    if await is_module_enabled(db, company_id, "inventory"):
        products = (
            await db.execute(
                select(Product.id, Product.name, Product.sku)
                .where(
                    Product.company_id == company_id,
                    or_(*(Product.name.ilike(p) for p in patterns), *(Product.sku.ilike(p) for p in patterns)),
                )
                .limit(MAX_RESULTS)
            )
        ).all()
        products_data = [{"id": str(p.id), "name": p.name, "sku": p.sku} for p in products]

    orders_data = []
    if await is_module_enabled(db, company_id, "orders"):
        orders = (
            await db.execute(
                select(Order.id, Order.order_number, Client.name.label("client_name"))
                .join(Client, Client.id == Order.client_id)
                .where(Order.company_id == company_id, Order.order_number.ilike(q.strip()))
                .limit(MAX_RESULTS)
            )
        ).all()
        orders_data = [
            {"id": str(o.id), "order_number": o.order_number, "client_name": o.client_name}
            for o in orders
        ]

    invoices_data = []
    if await is_module_enabled(db, company_id, "invoices"):
        invoices = (
            await db.execute(
                select(Invoice.id, Invoice.invoice_number, Client.name.label("client_name"))
                .join(Client, Client.id == Invoice.client_id)
                .where(Invoice.company_id == company_id, Invoice.invoice_number.ilike(q.strip()))
                .limit(MAX_RESULTS)
            )
        ).all()
        invoices_data = [
            {"id": str(i.id), "invoice_number": i.invoice_number, "client_name": i.client_name}
            for i in invoices
        ]

    suppliers_data = []
    if await is_module_enabled(db, company_id, "suppliers"):
        suppliers = (
            await db.execute(
                select(Supplier.id, Supplier.name, Supplier.identification_code)
                .where(
                    Supplier.company_id == company_id,
                    or_(
                        *(Supplier.name.ilike(p) for p in patterns),
                        *(Supplier.identification_code.ilike(p) for p in patterns),
                    ),
                )
                .limit(MAX_RESULTS)
            )
        ).all()
        suppliers_data = [
            {"id": str(s.id), "name": s.name, "identification_code": s.identification_code}
            for s in suppliers
        ]

    return ResponseBase(
        data={
            "clients": clients_data,
            "products": products_data,
            "orders": orders_data,
            "invoices": invoices_data,
            "suppliers": suppliers_data,
        }
    )
