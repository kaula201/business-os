# Business OS — ქართული ERP სისტემა

[![CI](https://github.com/kaula201/business-os/actions/workflows/ci.yml/badge.svg)](https://github.com/kaula201/business-os/actions/workflows/ci.yml)

სრულად ფუნქციონირებს Business OS — საოპერაციო სისტემა ქართული ბიზნესებისთვის. 34 მოდული, მოიცავს ფინანსებს (GL, ინვოისები, ბანკი), HR-ს, ფლოტს, საწყობს, CRM-ს, შეკვეთებს, რეპორტებს და AI ასისტენტს.

## ტექნოლოგიები

### Backend
- **Python 3.12** + **FastAPI**
- **PostgreSQL** (pgvector) + **SQLAlchemy** (async) + **asyncpg**
- **Redis** (caching/sessions/rate limiting)
- **JWT** authentication (python-jose + passlib)
- **Alembic** migrations (61)
- **ReportLab** (PDF), **OpenPyXL** (Excel)
- **OpenAI API** (AI ასისტენტი)

### Frontend
- **React 18** + **TypeScript**
- **Vite** (build tool)
- **Tailwind CSS**, **Zustand**, **TanStack Query**
- **Recharts**, **Lucide React**

### Infrastructure
- **Docker** + **Docker Compose**
- **GitHub Actions** CI (backend tests + frontend build)
- ავტომატური **PostgreSQL backup** ყოველ ღამეს (3:00)

## სწრაფი დაწყება (Docker)

```bash
git clone https://github.com/kaula201/business-os.git
cd business-os
docker compose up --build
```

ბრაუზერში გახსენით: **http://localhost:5173**

### Demo ანგარიში
- **Email:** admin@demo.ge
- **პაროლი:** admin123

> ⚠️ `.env.example`-დან დააკოპირეთ და შეავსეთ `backend/.env` რეალური secret-ებით (SECRET_KEY, OPENAI_API_KEY). სტანდარტული `secret` პაროლები მხოლოდ ლოკალური განვითარებისთვისაა.

## ლოკალური გაშვება (Development)

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# PostgreSQL უნდა იყოს გაშვებული (docker compose up postgres redis)
python -m app.migrate_schema
python seed.py
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## ტესტები

```bash
cd backend
pytest -q          # სრული სუიტა (PostgreSQL test DB მოითხოვს)
```

CI-ში ტესტები ავტომატურად ეშვება ყოველ push-ზე main-ზე.

## მოდულები (34)

| კატეგორია | მოდულები |
|---|---|
| **ფინანსები** | GL (Chart of Accounts, Journal Entries, Trial Balance, P&L, Balance Sheet), ინვოისები, მომწოდებლები/კლიენტების ფინანსები, ბანკი + რეკონსილაცია, ხელფასები, ბიუჯეტი, სალარო, ანალიტიკური აღრიცხვა, ვალუტა, ძირითადი საშუალებები |
| **ოპერაციები** | საწყობი, შეკვეთები, შესყიდვები, ხარჯები, წარმოება, პროექტები, POS |
| **კომერცია** | CRM, კლიენტები, მომწოდებლები, მარკეტინგი, აბონემენტები |
| **ადამიანური რესურსები** | თანამშრომლები, დასწრება, შვებულებები, რეკრუტინგი |
| **ორგანიზაცია** | დავალებები, helpdesk, დამტკიცებები (approvals), კონტრაქტები, დოკუმენტები |
| **სხვა** | ფლოტი, ანგარიშგებები, AI ასისტენტი, პარამეტრები, მომხმარებლები, პორტალი |

## API Endpoints

სრული დოკუმენტაცია ხელმისაწვდომია გაშვებულ backend-ზე:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## პროექტის სტრუქტურა

```
business-os/
├── docker-compose.yml          # postgres, redis, backend, frontend, backup
├── .github/workflows/ci.yml    # GitHub Actions CI
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # API endpoints (34 მოდული)
│   │   ├── models/             # SQLAlchemy models
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── core/               # Config, database, security, GL posting
│   │   └── services/           # ბიზნეს ლოგიკა
│   ├── migrations/             # Alembic migrations (61)
│   ├── tests/                  # Pytest tests
│   ├── seed.py                 # დემო მონაცემები
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/              # 37 page component
│   │   ├── components/         # UI components
│   │   ├── services/           # API client
│   │   ├── store/              # Zustand stores
│   │   └── types/              # TypeScript types
│   └── package.json
└── scripts/
    └── backup.sh               # ავტომატური backup
```

## ფუნქციონალი

- 📦 **საწყობი** — პროდუქტების CRUD, ნაშთის მართვა, კატეგორიები, barcode/GTIN
- 🛒 **შეკვეთები** — სასიცოცხლო ციკლი, მარაგის კონტროლი, ფინანსური დეტალები
- 📊 **GL** — გეგმა, ჟურნალის ჩანაწერები, საცდელი ბალანსი, P&L, ბალანსი
- 👥 **CRM** — ლიდები, pipeline, კონვერსია, stale lead alerts
- ✅ **დავალებები** — Kanban, კომენტარები
- 🤖 **AI ასისტენტი** — ბიზნეს ანალიზი (RAG)
- 📄 **ინვოისები** — PDF გენერაცია, VAT
- 🚗 **ფლოტი** — მანქანები, საწვავი, სერვისები, რუკა
- 👔 **HR** — თანამშრომლები, დასწრება, ხელფასები, ანალიტიკა
- 🔐 **ავტორიზაცია** — JWT, role-based access, rate limiting

## ლიცენზია

MIT
