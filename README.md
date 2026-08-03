# Business OS — ქართული ERP სისტემა

სრულად ფუნქციონირებს Business OS — საოპერაციო სისტემა ქართული ბიზნესებისთვის. მოიცავს საწყობის მართვას, შეკვეთებს, CRM-ს, დავალებებს, რეპორტებს და AI ასისტენტს.

## ტექნოლოგიები

### Backend
- **Python 3.12** + **FastAPI**
- **PostgreSQL** + **SQLAlchemy** (async) + **asyncpg**
- **Redis** (caching/sessions)
- **JWT** authentication (python-jose + passlib)
- **Alembic** migrations
- **ReportLab** (PDF generation)
- **OpenPyXL** (Excel export)
- **OpenAI API** (AI assistant)

### Frontend
- **React 18** + **TypeScript**
- **Vite** (build tool)
- **Tailwind CSS** (styling)
- **React Router** (routing)
- **Zustand** (state management)
- **TanStack Query** (data fetching)
- **Recharts** (charts)
- **Lucide React** (icons)

### Infrastructure
- **Docker** + **Docker Compose**

## სწრაფი დაწყება (Docker)

```bash
cd business-os
docker compose up --build
```

ბრაუზერში გახსენით: **http://localhost:5173**

### Demo ანგარიში
- **Email:** admin@demo.ge
- **პაროლი:** admin123

## ლოკალური გაშვება (Development)

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Database (PostgreSQL უნდა იყოს გაშვებული)
python -m app.seed
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## პროექტის სტრუქტურა

```
business-os/
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/    # API endpoints
│   │   │   ├── auth.py          # ავტორიზაცია
│   │   │   ├── products.py      # საწყობი
│   │   │   ├── orders.py        # შეკვეთები
│   │   │   ├── clients.py       # კლიენტები
│   │   │   ├── tasks.py         # დავალებები
│   │   │   ├── dashboard.py     # დაშბორდი
│   │   │   ├── ai.py            # AI ასისტენტი
│   │   │   ├── export.py        # Excel ექსპორტი
│   │   │   └── invoices.py      # ინვოისები (PDF)
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── core/                # Config, database, security
│   │   └── utils/               # PDF, Excel utilities
│   ├── tests/                   # Pytest tests
│   ├── seed.py                  # Database seed script
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/               # Page components
│   │   ├── components/          # UI components
│   │   ├── services/            # API client
│   │   ├── store/               # Zustand stores
│   │   └── types/               # TypeScript types
│   ├── .env
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
└── README.md
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/register | რეგისტრაცია |
| POST | /api/v1/auth/login | შესვლა |
| GET | /api/v1/products/ | პროდუქტების სია |
| POST | /api/v1/products/ | პროდუქტის შექმნა |
| PATCH | /api/v1/products/{id} | პროდუქტის განახლება |
| POST | /api/v1/products/adjust-stock | ნაშთის კორექტირება |
| GET | /api/v1/orders/ | შეკვეთების სია |
| POST | /api/v1/orders/ | შეკვეთის შექმნა |
| PATCH | /api/v1/orders/{id}/status | სტატუსის ცვლილება |
| GET | /api/v1/clients/ | კლიენტების სია |
| GET | /api/v1/dashboard/summary | დაშბორდის სტატისტიკა |
| POST | /api/v1/ai/chat | AI ასისტენტი |
| GET | /api/v1/export/products | Excel ექსპორტი |
| POST | /api/v1/invoices/{order_id}/generate | PDF ინვოისი |

## ტესტები

```bash
cd backend
pytest tests/ -v
```

## ფუნქციონალი

- 📦 **საწყობი** — პროდუქტების CRUD, ნაშთის მართვა, კატეგორიები
- 🛒 **შეკვეთები** — შეკვეთების შექმნა, სტატუსის მართვა, ინვოისები
- 👥 **CRM** — კლიენტების მართვა, კონტაქტი
- ✅ **დავალებები** — Kanban დოსკა, კომენტარები
- 📊 **რეპორტები** — გაყიდვები, სტატისტიკა, Excel ექსპორტი
- 🤖 **AI ასისტენტი** — ბიზნეს ანალიზი, რჩევები
- 📄 **ინვოისები** — PDF გენერაცია
- 🔐 **ავტორიზაცია** — JWT token, role-based access

## ლიცენზია

MIT
