# მოდული: AccountingControls (ბუღალტრული კონტროლები)

**კოდი:** `accounting-controls`
**Route:** `/accounting-controls`
**კატეგორია:** accounting
**დამოკიდებულია:** `consolidated`
**გვერდი:** `frontend/src/pages/AccountingControlsPage.tsx` (49 სტრიქონი)
**Backend:** `accounting_controls.py`

---

## მიზანი

ბუღალტრული კონტროლის პარამეტრები: ფისკალური პოზიციები, კონსოლიდაციის მაპინგები, ფიქსირებული კურსები (FX).

## გვერდის სტრუქტურა

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი ჩანაწერი" | ღილაკი | ახალი კონტროლის ჩანაწერი |
| „შენახვა" | ღილაკი | ჩანაწერის შენახვა |

## API Endpoints

### ფისკალური პოზიციები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/accounting-controls/fiscal-positions` | `list_fiscal_positions` |
| POST | `/accounting-controls/fiscal-positions` | `create_fiscal_position` |

### კონსოლიდაციის მაპინგები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/accounting-controls/consolidation-mappings` | `list_mappings` |
| POST | `/accounting-controls/consolidation-mappings` | `create_mapping` |

### ფიქსირებული კურსები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/accounting-controls/fx-rates` | `list_fx_rates` |
| POST | `/accounting-controls/fx-rates` | `create_fx_rate` |

## ბიზნეს ლოგიკა

- **ფისკალური პოზიცია:** განსაზღვრავს დღგ-ის მოპყრობას (მაგ. ექსპორტი — 0%)
- **მაპინგი:** კომპანიის ანგარიშების დაკავშირება კონსოლიდაციის ანგარიშებთან
- **FX კურსი:** ფიქსირებული კურსი კონსოლიდაციისთვის

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
