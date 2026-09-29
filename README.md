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

პირველი გაშვება ცარიელ volume-ზე:

1. Postgres იქმნება `POSTGRES_PASSWORD`-ით (superuser `business_os`).
2. ცალკე one-shot სერვისი `migrate` ეშვება `python -m app.core.migrate_schema`. მხოლოდ ამ კონტეინერს აქვს `MIGRATION_DATABASE_URL` (superuser, `POSTGRES_PASSWORD`-ისგან). ის ჯერ ქმნის `vector` და `pg_trgm` extension-ებს, შემდეგ `create_all`-ით მიმდინარე ORM სქემას, stamp-ს აკეთებს მხოლოდ `001_initial`-ზე და აგრძელებს `upgrade head`-მდე. Head-ზე stamp არ ხდება: RLS, `business_os_app`, grants, materialized view-ები და seed ჩანაწერები მიგრაციებშია და მოდელებში არა, ამიტომ head-ის stamp მათ გამოტოვებდა. ცარიელ ბაზაზე უკვე არსებული სვეტი (მაგალითად `supplier_payables.credited_amount` მიგრაცია 002-ში) დუბლიკატ DDL-ად გამოტოვდება. არსებულ ბაზაზე, რომელიც head-ს ჩამორჩება, იგივე მიგრაცია რეალურად ეშვება, რადგან ის სვეტი იქ ჯერ არ არის — `create_all` მხოლოდ ცარიელ ბაზაზე ხდება. შემდეგ იქმნება `business_os_app`, უფლებები (`ALTER DEFAULT PRIVILEGES` მომავალი ცხრილებისა და sequence-ებისთვის) და RLS. იმავე superuser სესიაში იქმნება read-only როლი `business_os_backup` (`LOGIN BYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE`, სქემაზე `USAGE`, ცხრილებსა და sequence-ებზე `SELECT`, materialized view-ებზე `SELECT`, `ALTER DEFAULT PRIVILEGES` მომავალი ობიექტებისთვის). `BYPASSRLS` მხოლოდ superuser-ს შეუძლია, ამიტომ ამ როლს migration `063` არ ქმნის. სერვისი exit 0-ით სრულდება.
3. `backend` იწყება მხოლოდ მაშინ, როცა `migrate` წარმატებით დასრულდა (`service_completed_successfully`). Backend-ის env-ში არის მხოლოდ `APP_DB_PASSWORD` და `DATABASE_URL` (`business_os_app`). `POSTGRES_PASSWORD`, `BACKUP_DB_PASSWORD` და superuser URL იქ არ ხვდება — superuser `NOBYPASSRLS`-ს გვერდს აუვლიდა, backup-ის პაროლი კი API პროცესს არ სჭირდება.

```bash
# Root `.env` (Compose interpolation). ცარიელი ან გამოტოვებული მნიშვნელობით
# `docker compose -f docker-compose.prod.yml` ჩერდება:
#   POSTGRES_PASSWORD   — Postgres superuser (`business_os`), მხოლოდ migrate სერვისი
#   APP_DB_PASSWORD     — როლი `business_os_app` (DATABASE_URL და MV refresh)
#   BACKUP_DB_PASSWORD  — როლი `business_os_backup` (მხოლოდ migrate და backup)
# სამი განსხვავებული ძლიერი პაროლი. გენერაცია:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
# ნუ გამოიყენებთ % ან $ (არც @ : / # ? და space). token_urlsafe მხოლოდ
# ასოებს, ციფრებს, "-" და "_" იყენებს.
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

### Backup და restore

`backup` კონტეინერი `pg_dump`-ს უშვებს როგორც `business_os_backup`. როლს აქვს `BYPASSRLS`, ამიტომ dump-ში ყველა tenant-ის სტრიქონი ხვდება. `--enable-row-security` არ გამოიყენება: ის ჩუმად არასრულ ან ცარიელ ფაილს წერს. უფლებები მხოლოდ `SELECT` და `USAGE`-ია — `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE` და DDL არ აქვს.

`scripts/backup.sh` იწყება `umask 077`-ით და შედეგ ფაილს სვამს `chmod 600`. ფაილი არის custom-format `pg_dump`, gzip-ით: `/backups/business_os_YYYYMMDD_HHMMSS.sql.gz`. Dump ინახავს owner-ს და ACL-ს. უფლებების წყარო მაინც migrate-ია: აღდგენის შემდეგ ის აბრუნებს როლებს სპეციფიკაციაზე. `pg_dumpall` და `-g` არ გამოიყენება, ამიტომ როლის პაროლის ჰეში dump-ში არ ხვდება. სკრიპტი იღებს `flock`-ს `/backups/.backup.lock`-ზე (mode 600). მეორე გაშვება ელოდება და არ შლის პირველის ცოცხალ `.partial` ფაილს. ერთ საათზე ძველი `.partial` იშლება.

`BACKUP_DB_PASSWORD` არის მხოლოდ `migrate` სერვისში (როლის პაროლის დასაყენებლად) და `backup` კონტეინერში. Backend-ში არ არის. `backup` კონტეინერს არ აქვს `POSTGRES_PASSWORD` და არც `APP_DB_PASSWORD`. Materialized view-ების `REFRESH` (`scripts/refresh_mvs.sh`) გადატანილია `mvrefresh` სერვისში, რადგან view-ების მფლობელია `business_os_app`, backup როლს კი ჩაწერა არ შეუძლია.

აღდგენას აკეთებს ოპერატორი superuser-ით (`business_os`), `scripts/restore.sh`-ით. Backup როლს restore-ის უფლება არ სჭირდება და არ აქვს. აღადგინეთ **ახალ** ბაზაში, არასოდეს `business_os`-ის ადგილზე. შეამოწმეთ, შემდეგ გადართეთ ტრაფიკი. აღადგინეთ მხოლოდ დასრულებული `.sql.gz` ფაილი და არასოდეს `.partial` ფაილი. პაროლი გადაეცემა გარემოთი ან `PGPASSFILE`-ით, არა არგუმენტით.

`restore.sh` რიგი:

1. მხოლოდ როლები (`RoleSpec` და env), Alembic-ის გარეშე, რომ სამიზნე ბაზა ცარიელი დარჩეს.
2. `pg_restore --exit-on-error --single-transaction` ცარიელ ბაზაში. შეცდომა ან შეწყვეტა ტრანზაქციას აბრუნებს; ნახევრად აღდგენილი ბაზა წარმატებად არ ითვლება.
3. სრული migrate. ის უფლებებს აბრუნებს სპეციფიკაციაზე და ძველ dump-ს head-მდე აჰყავს.

არაცარიელ სამიზნეს სკრიპტი უარყოფს. `--force-overwrite-nonempty` შლის ამ ბაზას და თავიდან ქმნის. სახელი `business_os` ყოველთვის უარყოფილია.

```bash
export PGHOST=127.0.0.1 PGPORT=5432 PGUSER=business_os
export APP_ENV=production
# PGPASSWORD, APP_DB_PASSWORD, BACKUP_DB_PASSWORD, JWT_SECRET_KEY, CORS_ORIGINS
# უკვე გარემოშია. არ ჩაწეროთ ისინი ბრძანების სტრიქონში.
scripts/restore.sh \
  --dump /path/business_os_YYYYMMDD_HHMMSS.sql.gz \
  --target-db business_os_restore
```

ყოველ superuser migrate-ზე, არა მხოლოდ როლის შექმნისას, თავიდან ენიჭება ატრიბუტები (`business_os_app`: `NOSUPERUSER NOBYPASSRLS`; `business_os_backup`: `LOGIN BYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE`), grants და default privileges. Backup როლზე ზედმეტი უფლება იხსნება (`SELECT`/`USAGE`-მდე). სამი materialized view-ის მფლობელი ხდება `business_os_app`. `company_id` ცხრილებზე თავიდან ედება `ENABLE`/`FORCE` RLS და `tenant_isolation`. Drift-ული ან კომპრომეტირებული dump-ის ზედმეტი უფლება აღდგენის შემდეგ არ რჩება. `--no-acl` dump-იც იგივე ნაბიჯით სწორდება.

არსებულ volume-ზე, სადაც `business_os_backup` ჯერ არ არის, შემდეგი წარმატებული `migrate` ქმნის როლს. ხელახალი გაშვება idempotent-ია. უკვე არსებული როლის პაროლს migrate არ ცვლის. `BACKUP_DB_PASSWORD`-ის შეცვლა env-ში მარტო როლის პაროლს არ ცვლის — იგივე წესი, რაც `business_os_app`-ზე. Superuser-ით: `ALTER ROLE business_os_backup PASSWORD '...';`.

სერტიფიკატის გამოშვება (DNS + CA) ოპერატორის ნაბიჯია. კონფიგურაცია მზადაა `nginx.prod.conf`-ში; სერტიფიკატის გარეშე nginx ვერ აიწყება.

არსებულ Postgres volume-ზე (პირველი init უკვე გავლილია) `POSTGRES_PASSWORD` superuser-ის პაროლს არ ცვლის — Postgres ამ ცვლადს მხოლოდ პირველ init-ზე კითხულობს, და `MIGRATION_DATABASE_URL`-იც ამ ახალ მნიშვნელობას იყენებს. სანამ ერთხელ, **ძველი** superuser პაროლით, არ გაუშვებთ `ALTER ROLE business_os PASSWORD '...';` (იგივე მნიშვნელობა, რაც ახალ `POSTGRES_PASSWORD`-შია), მიგრაცია ვერ შევა და superuser რჩება ძველ development პაროლზე `secret`. იმავე სესიაში, თუ როლი `business_os_app` ძველი პაროლითაა შექმნილი, migration `063` ხელახლა არ ეშვება — დააყენეთ `APP_DB_PASSWORD`-ის იგივე მნიშვნელობა: `ALTER ROLE business_os_app PASSWORD '...'`. `business_os_backup` ამ volume-ზე პირველ წარმატებულ `migrate`-ზე იქმნება `BACKUP_DB_PASSWORD`-ით. თუ როლი უკვე არსებობს, env-ში `BACKUP_DB_PASSWORD`-ის შეცვლა პაროლს არ ცვლის — `ALTER ROLE business_os_backup PASSWORD '...'`. შემდეგ თავიდან გაუშვით compose.

Production migration-ის დროს გამორთული დატოვეთ Postgres `log_statement=ddl` ან `all`, SQLAlchemy `echo` და Alembic offline `--sql`. Migration `063`-ის და migrate სერვისის `CREATE ROLE ... PASSWORD` (`business_os_app` და `business_os_backup`) ამ რეჟიმებში ლოგში ან გამოტანილ SQL-ში ჩანს.

## ლოკალური გაშვება (Development)

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# PostgreSQL უნდა იყოს გაშვებული (docker compose up postgres redis)
python -m app.core.migrate_schema
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
