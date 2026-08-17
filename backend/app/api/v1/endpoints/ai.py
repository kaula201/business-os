"""AI Assistant — OpenAI integration with Business OS context + RAG."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.core.time import utc_now
from app.models.user import User
from app.models.company import Company
from app.models.client import Client
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.task import Task
from app.schemas.ai import ChatRequest, ChatResponse
from app.schemas.common import ResponseBase
from app.core.config import settings
from app.services.rag import search_similar, index_company_data
from app.services.revenue import get_total_revenue
from datetime import datetime, timedelta
import json, uuid

router = APIRouter(prefix="/ai", tags=["AI ასისტენტი"])


async def _get_business_context(db: AsyncSession, user: User) -> str:
    """Collect business data for AI context."""
    company_id = user.company_id
    lines = []
    now = utc_now()

    # Company info
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if company:
        lines.append(f"კომპანია: {company.name} (ID: {company.identification_code})")

    # Client counts
    for status, label in [("active", "აქტიური"), ("potential", "პოტენციური"), ("inactive", "არააქტიური")]:
        cnt = (await db.execute(
            select(func.count()).where(Client.company_id == company_id, Client.status == status)
        )).scalar()
        lines.append(f"{label} კლიენტები: {cnt}")

    # Order stats
    total_orders = (await db.execute(
        select(func.count()).where(Order.company_id == company_id)
    )).scalar()
    lines.append(f"ჯამური შეკვეთები: {total_orders}")

    for status in OrderStatus:
        cnt = (await db.execute(
            select(func.count()).where(Order.company_id == company_id, Order.status == status.value)
        )).scalar()
        lines.append(f"  {status.value}: {cnt}")

    # Revenue — canonical issued-invoices semantic layer (last 30 days gross)
    revenue = await get_total_revenue(db, company_id)
    lines.append(f"ჯამური შემოსავალი (დადასტურებული ინვოისებიდან): {float(revenue):.2f} ₾")

    # Low stock products
    low_stock = (await db.execute(
        select(func.count()).where(
            Product.company_id == company_id,
            Product.current_stock <= Product.min_stock,
            Product.is_active == True
        )
    )).scalar()
    lines.append(f"დაბალი ნაშთის მქონე პროდუქტები: {low_stock}")

    # Overdue tasks
    overdue = (await db.execute(
        select(func.count()).where(
            Task.company_id == company_id,
            Task.due_date < now,
            Task.status.in_(["todo", "in_progress"])
        )
    )).scalar()
    lines.append(f"დაგვიანებული დავალებები: {overdue}")

    # Recent orders (top 3)
    recent = await db.execute(
        select(Order).where(Order.company_id == company_id)
        .order_by(desc(Order.created_at)).limit(3)
    )
    for o in recent.scalars():
        lines.append(f"  ბოლო: {o.order_number} — {o.status} — {float(o.total):.2f} ₾")

    return "\n".join(lines)


def _build_source_links(context: str) -> list[dict]:
    """Extract entity references from context and build frontend links."""
    links = []
    # Order references
    import re
    for match in re.finditer(r'ბოლო: (\S+)', context):
        links.append({"label": f"შეკვეთა {match.group(1)}", "url": "/orders"})
    # Client references
    for match in re.finditer(r'(აქტიური|პოტენციური|არააქტიური) კლიენტები', context):
        links.append({"label": "კლიენტების რეესტრი", "url": "/clients"})
    # Low stock
    if "დაბალი ნაშთი" in context:
        links.append({"label": "დაბალი ნაშთის პროდუქტები", "url": "/warehouses"})
    # Overdue tasks
    if "დაგვიანებული" in context:
        links.append({"label": "დაგვიანებული დავალებები", "url": "/tasks"})
    # Revenue
    if "შემოსავალი" in context:
        links.append({"label": "ფინანსური ანგარიშები", "url": "/gl/profit-loss"})
    return links


@router.post("/chat", response_model=ResponseBase[ChatResponse])
async def chat(
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI Assistant with OpenAI + business context."""
    conversation_id = data.conversation_id or str(uuid.uuid4())

    # Collect business context from DB
    context = await _get_business_context(db, current_user)

    # RAG: search for similar content using OpenAI or the local fallback.
    rag_results = await search_similar(
        db, current_user.company_id, data.message, limit=3
    )

    rag_context = ""
    if rag_results:
        rag_context = "\n\n**ნაპოვნი მონაცემები:**\n" + "\n".join(
            f"- [{r['type']}] {r['text']}" for r in rag_results
        )

    # If OpenAI key is not set, return mock (for testing)
    if not settings.OPENAI_API_KEY:
        import asyncio
        await asyncio.sleep(1)  # Simulate API latency
        source_links = _build_source_links(context)
        return ResponseBase(data=ChatResponse(
            message=f"🔍 **ბიზნეს მონაცემები:**\n\n{context}{rag_context}\n\n💡 **რჩევა:** ჩემი ანალიზის მიხედვით, თქვენ გაქვთ აქტიური ბიზნესი მრავალი კლიენტით. დაბალი ნაშთის მქონე პროდუქტების შესავსებად გადადით საწყობში.\n\n⚠️ **გაფრთხილება:** AI-ს მიერ მოწოდებული ფინანსური ინფორმაცია დაფუძნებულია მიმდინარე მონაცემებზე და არ წარმოადგენს ოფიციალურ ფინანსურ ანგარიშგებას. გადამოწმებისთვის იხილეთ შესაბამისი მოდული.",
            conversation_id=conversation_id,
            suggestions=["რა არის ჩემი მიმდინარე შეკვეთები?", "რომელ პროდუქტებს აქვთ დაბალი ნაშთი?", "მაჩვენე დაგვიანებული დავალებები"],
            source_links=source_links,
        ))

    try:
        import openai
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        system_prompt = f"""შენ ხარ Business OS AI ასისტენტი — ქართული ბიზნეს მართვის სისტემის ინტელექტუალური თანაშემწე.

შენი ამოცანაა დაეხმარო მომხმარებელს მისი ბიზნესის მონაცემების გაგებაში. უპასუხე მოკლედ, ზუსტად და ქართულად.

მომხმარებლის ბიზნესის მიმდინარე მონაცემები:
{context}
{rag_context}

წესები:
- უპასუხე მხოლოდ ქართულ ენაზე
- თუ მონაცემები არ გეყოფა პასუხისთვის, მიუთითე რა ინფორმაცია აკლია
- გამოიყენე emoji-ები პასუხის გასაფერადებლად
- შესთავაზე კონკრეტული ქმედებები (მაგ. "გადადით საწყობში შესავსებად")
- RAG-ით ნაპოვნი მონაცემები გამოიყენე პასუხის გასამდიდრებლად

მომხმარებლის როლი: {current_user.role}
როლის უფლებები:
- admin/owner: სრული წვდომა — შეგიძლია შესთავაზო ნებისმიერი მოქმედება
- manager: გაყიდვები, მარაგები, შეკვეთები — მაგრამ არა ფინანსური ოპერაციები (გადახდები, ბუღალტერია)
- accountant: ფინანსური მოდულები — მაგრამ არა გაყიდვები/მარაგების ცვლილება
- employee: მხოლოდ ნახვა — არ შესთავაზო შექმნა/რედაქტირება/წაშლა

მნიშვნელოვანი: არასოდეს შესთავაზო მოქმედება, რომელიც მომხმარებლის როლს არ აქვს უფლება შეასრულოს!"""

        messages = [
            {"role": "system", "content": system_prompt},
            *[{"role": m.role, "content": m.content} for m in (data.messages or [])],
            {"role": "user", "content": data.message},
        ]

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
        )

        answer = response.choices[0].message.content if response.choices else None
        if not answer or not answer.strip():
            answer = "AI-მ ცარიელი პასუხი დააბრუნა. გთხოვთ სცადოთ თავიდან ან შეცვალოთ შეკითხვა."

        source_links = _build_source_links(context)
        answer_with_disclaimer = answer.strip() + "\n\n⚠️ **გაფრთხილება:** AI-ს მიერ მოწოდებული ფინანსური ინფორმაცია დაფუძნებულია მიმდინარე მონაცემებზე და არ წარმოადგენს ოფიციალურ ფინანსურ ანგარიშგებას. გადამოწმებისთვის იხილეთ შესაბამისი მოდული."

        return ResponseBase(data=ChatResponse(
            message=answer_with_disclaimer,
            conversation_id=conversation_id,
            suggestions=[
                "რა არის ჩემი მიმდინარე შეკვეთები?",
                "რომელ პროდუქტს აქვს ყველაზე დაბალი ნაშთი?",
                "რამდენი კლიენტი მყავს?",
                "მაჩვენე დაგვიანებული დავალებები",
            ],
            source_links=source_links,
        ))

    except Exception as e:
        return ResponseBase(data=ChatResponse(
            message=f"❌ OpenAI-სთან დაკავშირების შეცდომა: {str(e)[:200]}",
            conversation_id=conversation_id,
            suggestions=[]
        ))


@router.get("/quick-actions", response_model=ResponseBase[list[dict]])
async def get_quick_actions():
    return ResponseBase(data=[
        {"id": "daily_summary", "label": "📊 დღის შეჯამება"},
        {"id": "critical_issues", "label": "🚨 კრიტიკული საკითხები"},
        {"id": "low_stock", "label": "📦 დაბალი ნაშთები"},
        {"id": "overdue_tasks", "label": "⏰ დაგვიანებული დავალებები"},
        {"id": "sales_report", "label": "💰 გაყიდვების ანგარიში"},
        {"id": "client_summary", "label": "👥 კლიენტების მიმოხილვა"},
    ])


@router.post("/reindex", response_model=ResponseBase[dict])
async def reindex_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("ai", "can_create")),
):
    """Re-index all business data for RAG search."""
    count = await index_company_data(db, current_user.company_id)
    return ResponseBase(data={"indexed_count": count, "message": f"დაინდექსირებულია {count} ჩანაწერი"})
