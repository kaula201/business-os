"""RAG service — embed business data and search via pgvector."""
import hashlib
import json
import math
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, func, desc, text, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.embedding import Embedding
from app.models.user import User
from app.models.company import Company
from app.models.client import Client
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.task import Task
from app.models.invoice import Invoice
from app.models.receivable import CustomerReceivable


# ── Embedding table metadata ─────────────────────────────────────────────────

embeddings_table = Embedding.__table__


def _local_embedding(text: str, dimensions: int = 1536) -> list[float]:
    """Deterministic lexical embedding used when OpenAI is unavailable."""
    normalized = text.lower().strip()
    words = re.findall(r"\w+", normalized, flags=re.UNICODE)
    features = words + [normalized[i:i + 3] for i in range(max(0, len(normalized) - 2))]
    vector = [0.0] * dimensions
    for feature in features or [normalized]:
        digest = hashlib.sha256(feature.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


async def _get_embedding(text: str) -> list[float]:
    """Return the single canonical embedding space used by index and search.

    RAG vectors intentionally stay local and deterministic.  Falling back from
    OpenAI per row/query would mix incompatible vector spaces in one index.
    OpenAI remains available to the chat-completion layer, not vector storage.
    """
    return _local_embedding(text)


# ── Content collectors ───────────────────────────────────────────────────────


async def _collect_clients(db: AsyncSession, company_id) -> list[dict]:
    result = await db.execute(
        select(Client)
        .where(Client.company_id == company_id, Client.deleted_at.is_(None))
        .options(selectinload(Client.contacts))
    )
    items = []
    for c in result.scalars().all():
        # Get primary contact info
        phone = ""
        email = ""
        if c.contacts:
            primary = next((ct for ct in c.contacts if ct.is_primary), c.contacts[0])
            phone = primary.phone or ""
            email = primary.email or ""
        items.append({
            "id": str(c.id),
            "text": f"კლიენტი: {c.name}, კოდი: {c.identification_code}, "
                    f"ტიპი: {'იურიდიული' if c.client_type == 'legal' else 'ფიზიკური'}, "
                    f"სტატუსი: {c.status}, ტელ: {phone}, ელ: {email}",
            "type": "client",
        })
    return items


async def _collect_products(db: AsyncSession, company_id) -> list[dict]:
    result = await db.execute(
        select(Product).where(Product.company_id == company_id, Product.is_active == True)
    )
    items = []
    for p in result.scalars().all():
        items.append({
            "id": str(p.id),
            "text": f"პროდუქტი: {p.name}, SKU: {p.sku}, "
                    f"ნაშთი: {p.current_stock} {p.unit}, მინ. ნაშთი: {p.min_stock}, "
                    f"გასაყიდი ფასი: {p.sale_price} ₾, "
                    f"შეძ. ფასი: {p.purchase_price or '—'} ₾",
            "type": "product",
        })
    return items


async def _collect_orders(db: AsyncSession, company_id) -> list[dict]:
    result = await db.execute(
        select(Order).where(Order.company_id == company_id)
        .order_by(desc(Order.created_at)).limit(50)
    )
    items = []
    for o in result.scalars().all():
        items.append({
            "id": str(o.id),
            "text": f"შეკვეთა: {o.order_number}, სტატუსი: {o.status}, "
                    f"თანხა: {o.total} ₾, შექმნილია: {o.created_at}",
            "type": "order",
        })
    return items


async def _collect_tasks(db: AsyncSession, company_id) -> list[dict]:
    result = await db.execute(
        select(Task).where(Task.company_id == company_id)
        .order_by(desc(Task.created_at)).limit(50)
    )
    items = []
    for t in result.scalars().all():
        items.append({
            "id": str(t.id),
            "text": f"დავალება: {t.title}, სტატუსი: {t.status}, "
                    f"პრიორიტეტი: {t.priority}, "
                    f"ვადა: {t.due_date or '—'}",
            "type": "task",
        })
    return items


async def _collect_invoices(db: AsyncSession, company_id) -> list[dict]:
    result = await db.execute(
        select(Invoice).where(Invoice.company_id == company_id)
        .order_by(desc(Invoice.created_at)).limit(50)
    )
    items = []
    for inv in result.scalars().all():
        items.append({
            "id": str(inv.id),
            "text": f"ინვოისი: {inv.invoice_number}, თანხა: {inv.total} ₾, "
                    f"სტატუსი: {inv.status}, გაცემის თარიღი: {inv.invoice_date}",
            "type": "invoice",
        })
    return items


async def _collect_receivables(db: AsyncSession, company_id) -> list[dict]:
    result = await db.execute(
        select(CustomerReceivable).where(CustomerReceivable.company_id == company_id)
        .order_by(desc(CustomerReceivable.created_at)).limit(50)
    )
    items = []
    for r in result.scalars().all():
        items.append({
            "id": str(r.id),
            "text": f"დებიტორული დავალიანება: {r.invoice_number}, "
                    f"კლიენტი: {r.client_name}, თანხა: {r.original_amount} ₾, "
                    f"გადახდილი: {r.paid_amount} ₾, ნაშთი: {r.outstanding_amount} ₾, "
                    f"სტატუსი: {r.status}",
            "type": "receivable",
        })
    return items


# ── Indexing ──────────────────────────────────────────────────────────────────


async def index_company_data(db: AsyncSession, company_id) -> int:
    """Re-index all business data for a company into the embeddings table."""
    # Clear old embeddings
    await db.execute(
        delete(embeddings_table).where(
            embeddings_table.c.company_id == company_id
        )
    )

    collectors = [
        _collect_clients, _collect_products, _collect_orders,
        _collect_tasks, _collect_invoices, _collect_receivables,
    ]

    all_items = []
    for collector in collectors:
        items = await collector(db, company_id)
        all_items.extend(items)

    # Generate every vector inline in the same transaction.  This guarantees
    # that the rows are searchable immediately after reindex commit and avoids
    # a background session racing the request transaction.
    for item in all_items:
        embedding = await _get_embedding(item["text"])
        await db.execute(
            embeddings_table.insert().values(
                company_id=company_id,
                content_type=item["type"],
                content_id=item["id"],
                content_text=item["text"],
                embedding=embedding,
            )
        )
    await db.flush()

    return len(all_items)


# ── Search ───────────────────────────────────────────────────────────────────


async def search_similar(db: AsyncSession, company_id, query: str, limit: int = 5) -> list[dict]:
    """Search for similar content using pgvector cosine similarity."""
    query_emb = await _get_embedding(query)
    if not query_emb:
        return []

    distance = Embedding.embedding.cosine_distance(query_emb)
    result = await db.execute(
        select(
            Embedding.content_type,
            Embedding.content_text,
            (1 - distance).label("similarity"),
        )
        .where(
            Embedding.company_id == company_id,
            Embedding.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(limit)
    )
    return [
        {"type": row[0], "text": row[1], "similarity": round(float(row[2]), 3)}
        for row in result.all()
    ]
