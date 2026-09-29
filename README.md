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

## სწრაფი დაწყება (Docker, development)

```bash
git clone https://github.com/kaula201/business-os.git
cd business-os
cp backend/.env.example backend/.env
# JWT_SECRET_KEY აუცილებელია — ცარიელი ან placeholder-ით აპი არ ეშვება:
# python -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose up --build
```

ბრაუზერში გახსენით: **http://localhost:5173**

`docker-compose.yml` არის ლოკალური განვითარების სტეკი (`APP_ENV=development`, Vite). Go-live ამ ფაილით არ ხდება.

### Demo ანგარიში
დემო მომხმარებლები (`admin@demo.ge` / `admin123`, `manager@demo.ge` / `manager123`) იქმნება მხოლოდ მაშინ, როცა `APP_ENV=development`. Production seed-ს არ უშვებს.

> ⚠️ `backend/.env`-ში ჩაწერეთ რეალური `JWT_SECRET_KEY` (არა `SECRET_KEY` — JWT ამ სახელს იყენებს) და `OPENAI_API_KEY`. `CORS_ORIGINS` უნდა იყოს მძიმით გამოყოფილი allowlist, `*` დაუშვებელია.

## Production (Docker Compose)

```bash
# Root `.env` (Compose interpolation). ცარიელი ან გამოტოვებული მნიშვნელობით
# `docker compose -f docker-compose.prod.yml` ჩერდება:
#   POSTGRES_PASSWORD  — Postgres superuser (`business_os`)
#   APP_DB_PASSWORD    — როლი `business_os_app` (DATABASE_URL, backup, MV refresh)
# ორი განსხვავებული ძლიერი პაროლი. APP_DB_PASSWORD-ში არ გამოიყენოთ @ : / # ? ან space.
cp .env.example .env
# backend/.env: APP_ENV-ს compose თავად სვამს production-ზე.
# აუცილებელია JWT_SECRET_KEY (32+ სიმბოლო), CORS_ORIGINS=https://your-domain,
# SAAS_WEBHOOK_SECRET. APP_DB_PASSWORD აქ ცარიელი დატოვეთ — prod compose root `.env`-დან სვამს.
mkdir -p certs
# განათავსეთ CA/Let's Encrypt სერტიფიკატები (რეპოში არ ინახება):
#   certs/fullchain.pem
#   certs/privkey.pem
docker compose -f docker-compose.prod.yml up --build
```

Production სტეკი:
- Postgres, Redis, backend და frontend **არ** ქვეყნდება ჰოსტის პორტებზე
- nginx უსმენს მხოლოდ 80 (ACME + redirect) და 443 (TLS)
- frontend არის `npm run build` + nginx, Vite HMR არ არის
- `/docs`, `/redoc`, `/openapi.json` გამორთულია
- ღია რეგისტრაცია გამორთულია (მოწვევა)
- SaaS webhook ხელმოწერის გარეშე 401-ს აბრუნებს

სერტიფიკატის გამოშვება (DNS + CA) ოპერატორის ნაბიჯია. კონფიგურაცია მზადაა `nginx.prod.conf`-ში; სერტიფიკატის გარეშე nginx ვერ აიწყება.

თუ Postgres volume უკვე არსებობს და როლი `business_os_app` ძველი პაროლითაა შექმნილი, migration `063` ხელახლა არ ეშვება. Superuser-ით ერთხელ დააყენეთ `APP_DB_PASSWORD`-ის იგივე მნიშვნელობა: `ALTER ROLE business_os_app PASSWORD '...'`.

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

Development-ში (`APP_ENV=development|test`):

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

`APP_ENV=production`-ში ეს სამი მისამართი არ რეგისტრირდება და 404-ს აბრუნებს. nginx-იც არ აპროქსირებს მათ.

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
- 🔐 **ავტორიზაცია** — JWT (`JWT_SECRET_KEY`, jti revoke), role-based access, TOTP 2FA, rate limiting

## ლიცენზია

MIT
