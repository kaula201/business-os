# მოდული: Inventory (საწყობი)

**კოდი:** `inventory`
**Route:** `/inventory`
**კატეგორია:** operations
**გვერდი:** `frontend/src/pages/InventoryPage.tsx` (762 სტრიქონი)
**Backend:** `warehouses.py`, `warehouses_enhanced.py`

---

## მიზანი

საწყობების, პროდუქტების და მარაგის მართვა: ნაშთები, გადატანა, კორექტირება, ინვენტარიზაცია, ზონები, დაბალი მარაგის გაფრთხილებები.

## გვერდის სტრუქტურა

### 1. პროდუქტები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| ძებნა | input | `productsApi.list({search})` |
| „ახალი პროდუქტი" | ღილაკი | შექმნის ფორმა |
| „Excel იმპორტი" | ღილაკი | პროდუქტების იმპორტი |
| „განახლება" | ღილაკი | პროდუქტის შენახვა |

### 2. საწყობები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი საწყობი" | ღილაკი | შექმნა |
| „მხოლოდ აქტიური" | ჩამრთველი | არქივირებულების დამალვა |
| „გადატანა" | ღილაკი | მარაგის გადატანა საწყობებს შორის (`transfer_stock`) |
| „დაამატეთ პირველი საწყობი" | ცარიელი მდგომარეობა | როცა საწყობი არ არსებობს |

### 3. ნაშთები და მოძრაობა

- `GET /warehouses/balances` — ნაშთები
- `GET /warehouses/movements` — მოძრაობის ისტორია
- `GET /warehouses/low-stock` — დაბალი მარაგის გაფრთხილებები

## API Endpoints

### საწყობები (`warehouses.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/warehouses/` | `list_warehouses` |
| POST | `/warehouses/` | `create_warehouse` |
| PATCH | `/warehouses/{id}` | `update_warehouse` |
| POST | `/warehouses/{id}/set-default` | `set_default_warehouse` |
| POST | `/warehouses/{id}/archive` | `archive_warehouse` |
| DELETE | `/warehouses/{id}` | `delete_warehouse` |
| GET | `/warehouses/balances` | `list_balances` |
| POST | `/warehouses/adjust-stock` | `adjust_warehouse_stock` — კორექტირება |
| POST | `/warehouses/transfers` | `transfer_stock` — გადატანა |
| GET | `/warehouses/movements` | `list_movements` |
| GET | `/warehouses/zones` | `list_zones` |
| POST | `/warehouses/zones` | `create_zone` |
| PATCH | `/warehouses/zones/{id}` | `update_zone` |
| DELETE | `/warehouses/zones/{id}` | `delete_zone` |
| GET | `/warehouses/zone-balances` | `list_zone_balances` |
| GET | `/warehouses/counts` | `list_counts` — ინვენტარიზაცია |
| POST | `/warehouses/counts` | `create_count` |
| PATCH | `/warehouses/counts/{id}` | `update_count` |
| GET | `/warehouses/counts/{id}` | `get_count` |
| GET | `/warehouses/counts/{id}/lines` | `list_count_lines` |
| POST | `/warehouses/counts/{id}/lines` | `add_count_line` |
| PATCH | `/warehouses/counts/{id}/lines/{line_id}` | `update_count_line` |
| DELETE | `/warehouses/counts/{id}/lines/{line_id}` | `delete_count_line` |
| POST | `/warehouses/counts/{id}/post` | `post_count` — დაფიქსირება |

### გაფართოებული (`warehouses_enhanced.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/warehouses/valuation` | `stock_valuation` — მარაგის შეფასება |
| GET | `/warehouses/movement-analytics` | `movement_analytics` |
| GET | `/warehouses/low-stock` | `low_stock_alerts` |
| GET | `/warehouses/export/balances` | `export_balances` |
| GET | `/warehouses/export/movements` | `export_movements` |

## Frontend API ზარები

- `productsApi.list({search})` — პროდუქტები
- `warehousesApi.list({include_inactive})` — საწყობები
- `purchaseCostsApi.list({product_id})` — შესყიდვის ფასები
- `productsApi.create/update` — პროდუქტის CRUD
- `warehousesApi.create/update/delete` — საწყობის CRUD

## ბიზნეს ლოგიკა

- **ინვენტარიზაცია:** count → lines → post (დაფიქსირება ცვლის ნაშთებს)
- **გადატანა:** მარაგი გადადის საწყობებს/ზონებს შორის
- **კორექტირება:** ხელით ნაშთის ჩასწორება (GL გატარებით)
- **ზონები:** საწყობის შიდა დაყოფა

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
