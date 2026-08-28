# მოდული: CRM (ლიდები და გაყიდვების pipeline)

**კოდი:** `crm`
**Route:** `/crm`
**კატეგორია:** sales
**გვერდი:** `frontend/src/pages/CRMPage.tsx` (499 სტრიქონი)
**Backend:** `crm.py`, `crm_enhanced.py`, `crm_export.py`

---

## მიზანი

ლიდების, შესაძლებლობების (opportunities) და აქტივობების მართვა — გაყიდვების pipeline-ის სრული ციკლი: ლიდი → კვალიფიკაცია → შესაძლებლობა → კლიენტი.

## გვერდის სტრუქტურა

### 1. ზედა ზოლი

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „CRM OS" | ბმული | გადასვლა CRM OS-ზე (ცალკე აპი, პორტი 5174) |
| „ახალი ლიდი" | ღილაკი | ლიდის შექმნის ფორმა |
| პერიოდის ფილტრი (· დღე) | select | ლიდების ფილტრი პერიოდის მიხედვით |
| „ყველას ნახვა" | ღილაკი | ფილტრის გასუფთავება |

### 2. ლიდების სია

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „გახსნა" | ღილაკი | ლიდის დეტალები |
| „დაკავშირებულად მონიშვნა" | ღილაკი | ლიდის სტატუსი → contacted |
| „კვალიფიცირება" | ღილაკი | ლიდის სტატუსი → qualified |
| „შესაძლებლობის შექმნა" | ღილაკი | ლიდიდან opportunity-ს შექმნა |
| „კლიენტად გადაყვანა" | ღილაკი | ლიდის კლიენტად კონვერტაცია |
| „შემდეგი მოქმედების დაგეგმვა" | ღილაკი | აქტივობის დაგეგმვა |
| „შესრულებულად მონიშვნა" | ღილაკი | აქტივობის დახურვა |
| „საკონტაქტო ინფორმაცია არ არის" | გაფრთხილება | ლიდს აკლია კონტაქტი |

### 3. ფორმები

- ლიდის ტიპი: იურიდიული / ფიზიკური (select: `legal` / `individual`)

## API Endpoints

### CRM ძირითადი (`crm.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| POST | `/crm/leads` | `create_lead` — ლიდის შექმნა |
| GET | `/crm/leads` | `list_leads` — ლიდების სია |
| PATCH | `/crm/leads/{lead_id}` | `update_lead` — ლიდის განახლება |
| POST | `/crm/leads/{lead_id}/convert` | `convert_lead` — კლიენტად გადაყვანა |
| POST | `/crm/opportunities` | `create_opportunity` |
| GET | `/crm/opportunities` | `list_opportunities` |
| PATCH | `/crm/opportunities/{id}` | `update_opportunity` |
| POST | `/crm/activities` | `create_activity` — აქტივობის შექმნა |
| GET | `/crm/activities` | `list_activities` |
| PATCH | `/crm/activities/{id}` | `update_activity` |

### CRM გაფართოებული (`crm_enhanced.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/crm/forecast` | `pipeline_forecast` — გაყიდვების პროგნოზი |
| GET | `/crm/pipeline-value` | `pipeline_value_by_stage` — pipeline-ის ღირებულება სტადიების მიხედვით |
| GET | `/crm/conversion-rate` | `conversion_rate` — კონვერტაციის კოეფიციენტი |
| GET | `/crm/lead-sources` | `lead_source_tracking` — ლიდების წყაროები |
| GET | `/crm/stale-leads` | `stale_leads` — უმოქმედო ლიდები |
| POST | `/crm/leads/bulk/status` | `bulk_update_lead_status` — მასობრივი სტატუსის ცვლილება |
| POST | `/crm/opportunities/bulk/stage` | `bulk_update_opportunity_stage` |
| POST | `/crm/leads/check-duplicates` | `check_duplicates` — დუბლიკატების შემოწმება |

### CRM ექსპორტი (`crm_export.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/crm/export/leads` | `export_leads` — ლიდების ექსპორტი |
| GET | `/crm/export/opportunities` | `export_opportunities` — შესაძლებლობების ექსპორტი |

## ბიზნეს ლოგიკა

- **ლიდის ციკლი:** new → contacted → qualified → opportunity → client
- **კონვერტაცია:** ლიდი → კლიენტი ქმნის ჩანაწერს კლიენტების რეესტრში
- **დუბლიკატების კონტროლი:** `check_duplicates` ამოწმებს არსებულ ლიდებს/კლიენტებს

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
