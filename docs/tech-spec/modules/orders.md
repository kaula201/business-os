# მოდული: Orders (გაყიდვის შეკვეთები)

**კოდი:** `orders`
**Route:** `/orders` (+ `/orders/:id`)
**კატეგორია:** sales
**დამოკიდებულია:** `clients`
**გვერდი:** `frontend/src/pages/OrdersPage.tsx` (511 სტრიქონი)
**Backend:** `orders.py`, `orders_enhanced.py`

---

## მიზანი

გაყიდვის შეკვეთების მართვა: შექმნა, სტატუსის ცვლილება, მარაგის შემოწმება, ინვოისად გადაქცევა, ისტორია და timeline.

## გვერდის სტრუქტურა

### 1. სიის ხედი

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| სტატუსის ფილტრი (ყველა / ...) | ღილაკების ჯგუფი | ფილტრავს სიას `status` პარამეტრით |
| „ახალი გაყიდვის შეკვეთა" | ღილაკი | შექმნის ფორმა |
| შეკვეთის რიგი | ცხრილი | ნომერი, კლიენტი, თარიღი, თანხა, სტატუსი |

### 2. შექმნის ფორმა

| ველი | ტიპი | წყარო |
|------|------|-------|
| კლიენტი | select | `clientsApi.list({page_size: 100})` |
| პროდუქტი | select | `productsApi.list({page_size: 100})` |
| საწყობი | select | `warehousesApi.list()` |
| რაოდენობა | input | |
| ფასი | input | |

| ღილაკი | ფუნქცია |
|--------|----------|
| „+ დამატება" | პოზიციის დამატება |
| „იქმნება..." | შეკვეთის შექმნა (`ordersApi.create`) |
| „გაუქმება" | ფორმის დახურვა |

### 3. შეკვეთის დეტალები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ინვოისის გახსნა" | ღილაკი | გადასვლა ინვოისზე |
| „დახურვა" | ღილაკი | დეტალების დახურვა |

## API Endpoints

### ძირითადი (`orders.py`)

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/orders/` | `list_orders` | სია (ფილტრები: status, page) |
| GET | `/orders/{order_id}` | `get_order` | ერთი შეკვეთა |
| POST | `/orders/` | `create_order` | შექმნა |
| PATCH | `/orders/{order_id}/status` | `change_order_status` | სტატუსის ცვლილება |
| GET | `/orders/stock-check` | `check_order_stock_availability` | მარაგის შემოწმება |
| GET | `/orders/lifecycle` | `get_order_lifecycle` | შეკვეთის სასიცოცხლო ციკლი |
| GET | `/orders/{order_id}/lifecycle` | `get_order_lifecycle_for_order` | ციკლი კონკრეტულზე |
| PATCH | `/orders/{order_id}/payment` | `update_order_payment` | გადახდის განახლება |
| GET | `/orders/{order_id}/timeline` | `get_order_timeline` | მოვლენების ქრონოლოგია |
| GET | `/orders/{order_id}/reservations` | `list_order_reservations` | მარაგის რეზერვაციები |
| GET | `/orders/{order_id}/history` | `list_order_history` | ცვლილებების ისტორია |

### გაფართოებული (`orders_enhanced.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/orders/analytics` | `order_analytics` — ანალიტიკა |
| POST | `/orders/bulk/status` | `bulk_update_order_status` — მასობრივი სტატუსი |
| GET | `/orders/export` | `export_orders` — ექსპორტი |

## Frontend API ზარები

- `ordersApi.list({status})` → GET `/orders/`
- `ordersApi.get(id)` → GET `/orders/{id}`
- `ordersApi.create(data)` → POST `/orders/`
- `clientsApi.list({page_size: 100})` — კლიენტების ჩამონათვალი
- `productsApi.list({page_size: 100})` — პროდუქტების ჩამონათვალი
- `warehousesApi.list()` — საწყობების ჩამონათვალი

## ბიზნეს ლოგიკა

- **სტატუსები:** draft → confirmed → ... (სრული ციკლი `lifecycle`-ში)
- **მარაგი:** `stock-check` ამოწმებს ხელმისაწვდომობას შექმნამდე
- **ინვოისად გადაქცევა:** შეკვეთიდან ინვოისის გენერაცია (`POST /invoices/generate`)
- **ისტორია:** ყველა ცვლილება ინახება და ჩანს timeline-ში

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
