# მოდული: SRS (SRS ანგარიშგება)

**კოდი:** `srs`
**Route:** `/srs`
**კატეგორია:** accounting
**დამოკიდებულია:** `gl`
**გვერდი:** `frontend/src/pages/SrsPage.tsx` (674 სტრიქონი)
**Backend:** `srs.py`, `tax_reports.py`

---

## მიზანი

საქართველოს საგადასახადო ანგარიშგება: დღგ-ის დეკლარაცია, საშემოსავლო გადასახადი, ბალანსის ფორმა, შეჯერება (reconciliation) და გაგზავნა.

## გვერდის სტრუქტურა

### 1. დღგ-ის დეკლარაცია

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| დეკლარაციის მონაცემები | ცხრილი | `GET /srs/vat-declaration` |
| გაყიდვების რეესტრი | ცხრილი | `GET /tax-reports/vat/register/sales` |
| შესყიდვების რეესტრი | ცხრილი | `GET /tax-reports/vat/register/purchases` |
| „გაგზავნა" | ღილაკი | `POST /srs/vat-declaration/submit` |
| „იგზავნება..." | ღილაკი | გაგზავნის პროცესი |
| „ექსპორტი" | ღილაკი | დეკლარაციის ექსპორტი |

### 2. საშემოსავლო გადასახადი

- `GET /srs/income-tax` — საშემოსავლო გადასახადის ანგარიში

### 3. ბალანსის ფორმა

- `GET /srs/balance-form` — ბალანსის ფორმა SRS-ისთვის

## API Endpoints

### SRS (`srs.py`)

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/srs/vat-declaration` | `vat_declaration` | დღგ-ის დეკლარაცია |
| GET | `/srs/income-tax` | `income_tax_report` | საშემოსავლო გადასახადი |
| GET | `/srs/balance-form` | `balance_form` | ბალანსის ფორმა |
| GET | `/srs/reconciliation` | `srs_reconciliation` | შეჯერება |
| GET | `/srs/status` | `srs_status` | სტატუსი |
| POST | `/srs/vat-declaration/submit` | `submit_vat_declaration` | გაგზავნა |

### საგადასახადო რეპორტები (`tax_reports.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/tax-reports/vat` | `vat_return` — დღგ-ის დაბრუნება |
| GET | `/tax-reports/vat/register/sales` | `sales_vat_register` — გაყიდვების რეესტრი |
| GET | `/tax-reports/vat/register/purchases` | `purchases_vat_register` — შესყიდვების რეესტრი |

## ბიზნეს ლოგიკა

- დეკლარაცია ითვლება GL ჩანაწერებიდან (დღგ-ის ანგარიშები)
- გაგზავნა ხდება SRS-ის სისტემაში (ინტეგრაცია `rs_ge.py` სერვისით)

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
