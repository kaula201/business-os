# მოდული: Dashboard (მიმოხილვა)

**კოდი:** `dashboard`
**Route:** `/dashboard`
**კატეგორია:** main
**გვერდი:** `frontend/src/pages/DashboardPage.tsx` (372 სტრიქონი)
**Backend:** `dashboard.py`, `dashboard_enhanced.py`

---

## მიზანი

მთავარი სამუშაო მაგიდა — კომპანიის მდგომარეობის ერთი შეხედვით მიმოხილვა: შემოსავალი, კლიენტები, შეკვეთები, დავალებები, ფულადი ნაკადი, დავალიანებები.

## გვერდის სტრუქტურა

### 1. ზედა ზოლი (Header)

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| სათაური „მიმოხილვა" | ტექსტი | გვერდის სათაური |
| პასუხისმგებელი ფილტრი | select | ფილტრავს KPI-ებს თანამშრომლის მიხედვით (`owner_id` პარამეტრი) |
| პერიოდის არჩევა (7 დღე / 30 დღე / 90 დღე) | ღილაკების ჯგუფი | ცვლის მონაცემების პერიოდს (`period` პარამეტრი) |
| „მორგება" | ღილაკი | ხსნის/ხურავს KPI ბარათების მორგების პანელს |

### 2. KPI ბარათები

ჩვენება: შემოსავალი, აქტიური კლიენტები, მიმდინარე შეკვეთები, დაგვიანებული დავალებები.

- თითოეულ ბარათს აქვს ტენდენციის ისარი (წინა პერიოდთან შედარებით)
- „დეტალურად ნახვა" ღილაკი — გადაჰყავს შესაბამის მოდულში
- **მორგება:** KPI ბარათების დამალვა/ჩვენება — ინახება `localStorage`-ში (`bos_hidden_kpis`)

### 3. შემოსავლის გრაფიკი

- ტიპი: ხაზოვანი/სვეტოვანი დიაგრამა (Recharts)
- მონაცემები: `GET /dashboard/summary` → `revenue_chart.data`

### 4. შეკვეთების სტატუსის განაწილება

- ტიპი: წრიული დიაგრამა (Pie)
- მონაცემები: `GET /dashboard/summary` → `order_status_distribution`

### 5. კრიტიკული შეტყობინებები (Alerts)

- სია: დაგვიანებული გადახდები, დაბალი მარაგი, ვადაგასული დავალებები
- მონაცემები: `GET /dashboard/summary` → `critical_alerts`

### 6. დავალიანებების ასაკი (Aging)

- მონაცემები: `GET /dashboard/aging`
- ჯგუფები: 0-30, 31-60, 61-90, 90+ დღე

### 7. ფულადი ნაკადი (Cash Flow)

- მონაცემები: `GET /dashboard/cash-flow`
- შემოსავლები vs ხარჯები პერიოდების მიხედვით

## API Endpoints

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/dashboard/summary` | `get_dashboard_summary` | KPI + გრაფიკები + alerts (პარამეტრები: `period`, `owner_id`) |
| GET | `/dashboard/aging` | `aging_summary` | დავალიანებების ასაკობრივი განაწილება |
| GET | `/dashboard/cash-flow` | `cash_flow` | ფულადი ნაკადის მონაცემები |
| GET | `/dashboard/extended-kpis` | `extended_kpis` | დამატებითი KPI-ები |
| GET | `/dashboard/quick-actions` | `quick_actions` | სწრაფი მოქმედებების სია |
| GET | `/dashboard/export/summary` | `export_dashboard_summary` | მიმოხილვის ექსპორტი |
| GET | `/dashboard/drill-down/{entity}` | `drill_down` | დეტალური მონაცემები ერთეულზე |
| POST | `/dashboard/refresh-views` | `refresh_views` | Materialized views-ის ხელით განახლება |

## Frontend API ზარები

- `dashboardApi.getSummary(period, ownerId)` → `GET /dashboard/summary`
- `dashboardApi.getAging()` → `GET /dashboard/aging`
- `dashboardApi.getCashFlow()` → `GET /dashboard/cash-flow`
- `usersApi.list({page_size: 100})` → თანამშრომლების სია ფილტრისთვის

## ბიზნეს ლოგიკა

- KPI მონაცემები ითვლება backend-ში (მათ შორის materialized views-იდან: `mv_sales_daily` და სხვა)
- ვალუტის ფორმატი: `Intl.NumberFormat('ka-GE', {currency: 'GEL'})` — „590 ₾"
- ფერები: ბრენდის პალიტრა `#16A6D4`, `#4CAF32` და სხვა

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
