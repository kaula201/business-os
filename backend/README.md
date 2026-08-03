# Business OS — Backend

## არქიტექტურა

```
backend/
├── app/
│   ├── api/v1/endpoints/    # API route handlers
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── companies.py
│   │   ├── clients.py
│   │   ├── orders.py
│   │   ├── products.py
│   │   ├── inventory.py
│   │   ├── tasks.py
│   │   ├── reports.py
│   │   ├── dashboard.py
│   │   ├── ai.py
│   │   └── settings.py
│   ├── core/                # კონფიგი, უსაფრთხოება
│   │   ├── config.py
│   │   ├── security.py
│   │   └── database.py
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py
│   │   ├── company.py
│   │   ├── client.py
│   │   ├── order.py
│   │   ├── product.py
│   │   ├── task.py
│   │   └── audit.py
│   ├── schemas/             # Pydantic schemas
│   │   ├── user.py
│   │   ├── client.py
│   │   ├── order.py
│   │   ├── product.py
│   │   ├── task.py
│   │   └── common.py
│   ├── services/            # Business logic
│   │   ├── auth_service.py
│   │   ├── client_service.py
│   │   ├── order_service.py
│   │   ├── product_service.py
│   │   ├── task_service.py
│   │   ├── report_service.py
│   │   └── dashboard_service.py
│   ├── ai/                  # AI ასისტენტი
│   │   ├── agent.py
│   │   ├── prompts.py
│   │   └── rag.py
│   └── utils/               # დამხმარე ფუნქციები
│       ├── pdf.py
│       └── excel.py
├── tests/
│   ├── unit/
│   └── integration/
├── requirements.txt
├── Dockerfile
└── README.md
```

## ტექნოლოგიები

- **Framework:** FastAPI
- **Database:** PostgreSQL + SQLAlchemy (async)
- **Cache:** Redis
- **Auth:** JWT (python-jose + passlib)
- **AI:** OpenAI API + RAG (pgvector)
- **PDF:** WeasyPrint / ReportLab
- **Excel:** openpyxl
- **Migrations:** Alembic
- **Testing:** pytest + httpx
