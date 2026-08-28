# მოდული: Reports (რეპორტები)

**კოდი:** `reports`
**Route:** `/reports`
**კატეგორია:** other
**გვერდი:** `frontend/src/pages/ReportsPage.tsx` (387 სტრიქონი)
**Backend:** `reports.py`

---

## მიზანი

ანალიტიკური რეპორტები: შემოსავლები/ხარჯები, განზომილებები (მთვარე, ფილიალი, პროდუქტი, მენეჯერი), pivot ცხრილები, შენახული რეპორტები, განრიგები (schedules), ექსპორტი.

## გვერდის სტრუქტურა

### 1. რეპორტის არჩევა

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| რეპორტის ტიპი | select | revenue / expenses |
| განზომილება | select | month / branch / product / manager |
| პერიოდი | input (date range) | |

### 2. ექსპორტი

| ღილაკი | ფუნქცია |
|--------|----------|
| „Excel ექსპორტი" | მიმდინარე რეპორტის ექსპორტი |
| „ექსპორტი" | ზოგადი ექსპორტი |
| „Excel" (x4) | სხვადასხვა სექციის ექსპორტი |

## API Endpoints

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/reports/summary` | `reports_summary` | შეჯამება |
| GET | `/reports/revenue` | `reports_revenue` | შემოსავლების რეპორტი |
| GET | `/reports/definitions` | `reports_definitions` | რეპორტების განმარტებები |
| GET | `/reports/export-scope` | `get_export_scope` | ექსპორტის ფარგლები |
| PATCH | `/reports/export-scope` | `update_export_scope` | |
| GET | `/reports/saved` | `list_saved_reports` | შენახული რეპორტები |
| POST | `/reports/saved` | `create_saved_report` | |
| DELETE | `/reports/saved/{report_id}` | `delete_saved_report` | |
| GET | `/reports/schedules` | `list_schedules` | განრიგები |
| POST | `/reports/schedules` | `create_schedule` | |
| GET | `/reports/dimensions` | `list_dimensions` | განზომილებები |
| POST | `/reports/dimensions` | `create_dimension` | |
| GET | `/reports/pivot` | `pivot_report` | pivot ცხრილი |

## Frontend API ზარები

- `ordersApi.list({page_size: 100})` — შეკვეთების მონაცემები
- `productsApi.list({page_size: 100})` — პროდუქტები
- `clientsApi.list({page_size: 100})` — კლიენტები
- `tasksApi.list({page_size: 100})` — დავალებები

## ბიზნეს ლოგიკა

- **განზომილებები:** რეპორტის დაჯგუფება მთვარის/ფილიალის/პროდუქტის/მენეჯერის მიხედვით
- **Pivot:** მრავალგანზომილებიანი ცხრილი
- **შენახული რეპორტები:** პარამეტრების შენახვა ხელახალი გამოყენებისთვის
- **განრიგები:** პერიოდული რეპორტების ავტომატური გენერაცია

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
