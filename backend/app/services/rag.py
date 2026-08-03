"""RAG service — embed business data and search via pgvector."""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import MetaData, Table, Column, String, Text, DateTime, ForeignKey, UniqueConstraint, select, func, desc, text, delete
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.user import User
from app.models.company import Company
from app.models.client import Client
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.task import Task
from app.models.invoice import Invoice
from app.models.receivable import CustomerReceivable


# ── Embedding table metadata (no ORM model needed) ───────────────────────────


_metadata = MetaData()
embeddings_table = Table(
    "embeddings", _metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("company_id", UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False),
    Column("content_type", String(50), nullable=False),
    Column("content_id", UUID(as_uuid=True), nullable=False),
    Column("content_text", Text(), nullable=False),
    Column("embedding", Text(), nullable=True),
    Column("created_at", DateTime(), nullable=False),
    Column("updated_at", DateTime(), nullable=False),
)


async def _get_embedding(text: str) -> list[float] | None:
    """Get embedding vector from OpenAI."""
    if not settings.OPENAI_API_KEY:
        return None
    try:
        import openai
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=text[:8000],  # Truncate to token limit
        )
        return response.data[0].embedding
    except Exception:
        return None


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

    # Batch insert without embeddings (they'll be filled asynchronously)
    for item in all_items:
        await db.execute(
            embeddings_table.insert().values(
                company_id=company_id,
                content_type=item["type"],
                content_id=item["id"],
                content_text=item["text"],
            )
        )
    await db.flush()

    # Generate embeddings in background (best-effort)
    if settings.OPENAI_API_KEY:
        asyncio.create_task(_fill_embeddings(db.bind, company_id))

    return len(all_items)


async def _fill_embeddings(bind, company_id):
    """Background task: generate embeddings for unembedded rows."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    async with async_sessionmaker(bind, class_=AsyncSession)() as session:
        result = await session.execute(
            select(embeddings_table.c.id, embeddings_table.c.content_text)
            .where(
                embeddings_table.c.company_id == company_id,
                embeddings_table.c.embedding.is_(None),
            )
        )
        rows = result.all()
        for row_id, text in rows:
            emb = await _get_embedding(text)
            if emb:
                await session.execute(
                    embeddings_table.update()
                    .where(embeddings_table.c.id == row_id)
                    .values(embedding=emb)
                )
        await session.commit()


# ── Search ───────────────────────────────────────────────────────────────────


async def search_similar(db: AsyncSession, company_id, query: str, limit: int = 5) -> list[dict]:
    """Search for similar content using pgvector cosine similarity."""
    query_emb = await _get_embedding(query)
    if not query_emb:
        return []

    # Use pgvector cosine similarity search
    emb_str = "[" + ",".join(str(x) for x in query_emb) + "]"
    sql = text("""
        SELECT content_type, content_text, 1 - (embedding <=> :emb::vector) AS similarity
        FROM embeddings
        WHERE company_id = :company_id AND embedding IS NOT NULL
        ORDER BY embedding <=> :emb::vector
        LIMIT :limit
    """)
    result = await db.execute(sql, {"emb": emb_str, "company_id": company_id, "limit": limit})
    return [
        {"type": row[0], "text": row[1], "similarity": round(float(row[2]), 3)}
        for row in result.all()
    ]
