# მოდული: Procurement (შესყიდვები — Procurement)

**კოდი:** `procurement`
**Route:** `/procurement`
**კატეგორია:** purchases
**დამოკიდებულია:** `suppliers`
**გვერდი:** `frontend/src/pages/ProcurementPage.tsx` (788 სტრიქონი)
**Backend:** `procurement.py`, `tenders.py`, `contracts.py`

---

## მიზანი

მოწინავე შესყიდვების მართვა: RFQ (Request for Quotation), vendor ფასები, ჩარჩო შეთანხმებები (blanket orders), სკორკარდები, ხელშეკრულებები, ტენდერები, vendor ანალიტიკა, ავტო-შევსება.

## გვერდის სტრუქტურა

### 1. ტაბები

| ტაბი | ფუნქცია |
|------|----------|
| „RFQ" | მოთხოვნა ფასებზე |
| „Vendor ფასები" | მომწოდებლების ფასების სიები |
| „ჩარჩო შეთანხმებები" | blanket orders |
| „სკორკარდები" | მომწოდებლების შეფასება |
| „ხელშეკრულებები" | კონტრაქტები |
| „ტენდერები" | ტენდერები |
| „Vendor ანალიტიკა" | ანალიტიკა |

### 2. RFQ

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი RFQ" | ღილაკი | შექმნა (`POST /procurement/rfqs`) |
| „გამოქვეყნება" | ღილაკი | მომწოდებლებზე გაგზავნა (`send_rfq_email`) |
| „ისტორია" | ღილაკი | RFQ-ს ისტორია |
| „ავტომატური გამოთვლა" | ღილაკი | სკორკარდების ავტო გამოთვლა |
| „აქტივაცია" | ღილაკი | ჩარჩო შეთანხმების აქტივაცია |

### 3. ფორმები

| ველი | ტიპი | წყარო |
|------|------|-------|
| მომწოდებელი | select | `suppliersApi.list({page_size: 200})` |
| პროდუქტი | select | `productsApi.list({page_size: 200})` |
| ვალუტა | select | GEL / USD / EUR |
| ხელშეკრულება | select | `contractsApi.list({page_size: 100})` |

## API Endpoints

### RFQ (`procurement.py`)

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| POST | `/procurement/rfqs` | `create_rfq` | RFQ-ს შექმნა |
| GET | `/procurement/rfqs` | `list_rfqs` | სია |
| POST | `/procurement/rfqs/{rfq_id}/responses` | `submit_rfq_response` | მომწოდებლის პასუხი |
| POST | `/procurement/rfqs/{rfq_id}/send-email` | `send_rfq_email` | გაგზავნა |
| GET | `/procurement/rfqs/{rfq_id}/comparison` | `rfq_comparison` | შედარება |
| POST | `/procurement/rfqs/{rfq_id}/award` | `award_rfq` | გამარჯვებულის გამოცხადება |

### Vendor ფასები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| POST | `/procurement/price-lists` | `upsert_price_list` |
| GET | `/procurement/price-lists` | `list_price_lists` |
| GET | `/procurement/price-trend` | `price_trend` — ფასების ტენდენცია |

### ჩარჩო შეთანხმებები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| POST | `/procurement/blanket-orders` | `create_blanket_order` |
| GET | `/procurement/blanket-orders` | `list_blanket_orders` |
| POST | `/procurement/blanket-orders/{id}/activate` | `activate_blanket_order` |

### სკორკარდები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| POST | `/procurement/scorecards` | `upsert_scorecard` |
| GET | `/procurement/scorecards` | `list_scorecards` |
| POST | `/procurement/scorecards/auto-calculate` | `auto_calculate_scorecards` |

### ავტო-შევსება

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| POST | `/procurement/auto-replenish` | `auto_replenish` |

### Vendor ანალიტიკა (`vendor_analytics.py`)

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/procurement/vendor-analytics` | `vendor_analytics` | აგრეგირებული ანალიტიკა მომწოდებლების მიხედვით: ხარჯი, დროული მიწოდება, ხარისხი, ფასის ტენდენცია (ფილტრები: `date_from`, `date_to`) |

### ტენდერები (`tenders.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| POST | `/procurement/tenders/{id}/publish` | `publish_tender` |
| POST | `/procurement/tenders/{id}/bids` | `submit_bid` |
| GET | `/procurement/tenders/{id}/comparison` | `tender_comparison` |
| POST | `/procurement/tenders/{id}/award` | `award_tender` |

### ხელშეკრულებები (`contracts.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/contracts/` | `list_contracts` |
| GET | `/contracts/{contract_id}` | `get_contract` |
| POST | `/contracts/` | `create_contract` |
| PATCH | `/contracts/{contract_id}` | `update_contract` |
| DELETE | `/contracts/{contract_id}` | `delete_contract` |

## Frontend API ზარები

- `contractsApi.list({page_size: 100})` — ხელშეკრულებები
- `productsApi.list({page_size: 200})` — პროდუქტები
- `suppliersApi.list({page_size: 200})` — მომწოდებლები
- `contractsApi.create({title, ...})` — ხელშეკრულების შექმნა

## ბიზნეს ლოგიკა

- **RFQ ციკლი:** შექმნა → გაგზავნა მომწოდებლებზე → პასუხები → შედარება → award
- **ჩარჩო შეთანხმება:** წინასწარ შეთანხმებული ფასები/პირობები — აქტივაციის შემდეგ გამოიყენება PO-ებში
- **სკორკარდები:** მომწოდებლის შეფასება კრიტერიუმებით (ფასი, ხარისხი, დროულობა) — ავტო გამოთვლა ისტორიული მონაცემებიდან
- **ტენდერი:** გამოქვეყნება → ბიდები → შედარება → award
- **ავტო-შევსება:** დაბალი მარაგისას ავტომატური შესყიდვის წინადადება

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
