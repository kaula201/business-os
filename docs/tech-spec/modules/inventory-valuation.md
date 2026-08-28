# მოდული: InventoryValuation (მარაგების შეფასება)

**კოდი:** `inventory-valuation`
**Route:** `/inventory-valuation`
**კატეგორია:** operations
**დამოკიდებულია:** `inventory`
**გვერდი:** `frontend/src/pages/InventoryValuationPage.tsx` (171 სტრიქონი)
**Backend:** `inventory_valuation.py`

---

## მიზანი

მარაგების ღირებულების შეფასება WAC (Weighted Average Cost) მეთოდით — თითოეული პროდუქტის საშუალო შესყიდვის ფასი და მარაგის მთლიანი ღირებულება.

## გვერდის სტრუქტურა

### 1. შეფასების სია

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| პროდუქტის არჩევა | select | `productsApi.list({page_size: 100})` |
| შეფასების ცხრილი | ცხრილი | პროდუქტი, რაოდენობა, WAC ფასი, ჯამური ღირებულება |

### 2. კორექტირება

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „კორექტირება" | ღილაკი | ღირებულების ხელით კორექტირება (`POST /inventory/valuation/adjust`) |
| „შენახვა" | ღილაკი | კორექტირების შენახვა |

## API Endpoints

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/inventory/valuation/summary` | `valuation_summary` | მთლიანი შეფასება |
| GET | `/inventory/valuation/{product_id}` | `get_product_valuation` | ერთი პროდუქტის შეფასება |
| POST | `/inventory/valuation/adjust` | `adjust_valuation` | კორექტირება |

## Frontend API ზარები

- `productsApi.list({page_size: 100})` — პროდუქტების სია
- `inventoryValuationApi.get(selectedId)` → GET `/inventory/valuation/{id}`

## ბიზნეს ლოგიკა

- **WAC:** საშუალო შეწონილი ღირებულება = მარაგის ჯამური ღირებულება / ჯამური რაოდენობა
- **COGS:** გაყიდვისას ხარჯი ითვლება WAC ფასით
- **კორექტირება:** ხელით ჩასწორება ქმნის GL გატარებას (მარაგის ანგარიშზე)
- **შესყიდვის ფასი:** იღება მომწოდებლის ინვოისებიდან (`purchase_costs`)

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
