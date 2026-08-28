# მოდული: Purchases (შესყიდვები)

**კოდი:** `purchases`
**Route:** `/purchases` (+ `/purchases/:id`)
**კატეგორია:** purchases
**გვერდი:** `frontend/src/pages/PurchasesPage.tsx` (448 სტრიქონი)
**Backend:** `purchase_orders.py`, `quality_control.py`

---

## მიზანი

შესყიდვის შეკვეთების (Purchase Orders) სრული სასიცოცხლო ციკლი: შექმნა, დამტკიცება, საქონლის მიღება (goods receipt), ხარისხის შემოწმება, სამმხრივი შეჯერება (three-way match), მომწოდებლის ინვოისი.

## გვერდის სტრუქტურა

### 1. სიის ხედი

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| ძებნა | input | `purchaseOrdersApi.list({search})` |
| „ახალი შესყიდვის შეკვეთა" | ღილაკი | შექმნის ფორმა |
| შეკვეთის რიგი | ცხრილი | ნომერი, მომწოდებელი, თარიღი, თანხა, სტატუსი |

### 2. შექმნის ფორმა

| ველი | ტიპი | წყარო |
|------|------|-------|
| მომწოდებელი | select | `suppliersApi.list({page_size: 100})` |
| საწყობი | select | `warehousesApi.list()` |
| პროდუქტი | select | `productsApi.list({page_size: 100})` |
| რაოდენობა | input | |
| ფასი | input | |

| ღილაკი | ფუნქცია |
|--------|----------|
| „ხაზის დამატება" | პოზიციის დამატება |
| „იქმნება..." | შეკვეთის შექმნა (`purchaseOrdersApi.create`) |
| „გაუქმება" | ფორმის დახურვა |

### 3. შეკვეთის დეტალები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „დამტკიცება" | ღილაკი | შეკვეთის დამტკიცება |
| „საქონლის მიღება" | ღილაკი | მიღების ფორმა (`post_goods_receipt`) |
| „მიღების გაგრძელება" | ღილაკი | ნაწილობრივი მიღების გაგრძელება |
| „მიღება მუშავდება..." | ღილაკი | მიღების დადასტურება |
| „ხარისხის შემოწმება" | ღილაკი | QC ფორმა (`quality_check_receipt`) |
| „სამმხრივი შეჯერება" | ღილაკი | PO vs მიღება vs ინვოისი (`get_three_way_match`) |
| „მომწოდებლის ინვოისი" | ღილაკი | ინვოისის შექმნა/მიბმა |

### 4. ხარისხის შემოწმება

| ველი | ტიპი | შესაძლო მნიშვნელობები |
|------|------|------------------------|
| შედეგი | select | passed / failed / partial / pending |

## API Endpoints

### შეკვეთები (`purchase_orders.py`)

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/purchase-orders/` | `list_purchase_orders` | სია |
| POST | `/purchase-orders/` | `create_purchase_order` | შექმნა |
| GET | `/purchase-orders/{id}` | `get_purchase_order` | ერთი შეკვეთა |
| GET | `/purchase-orders/{id}/history` | `get_purchase_order_history` | ისტორია |
| PATCH | `/purchase-orders/{id}/status` | `change_purchase_order_status` | სტატუსის ცვლილება |
| GET | `/purchase-orders/{id}/receipts` | `list_goods_receipts` | მიღებები |
| POST | `/purchase-orders/{id}/receipts` | `post_goods_receipt` | საქონლის მიღება |
| POST | `/purchase-orders/{id}/receipts/{receipt_id}/quality-check` | `quality_check_receipt` | ხარისხის შემოწმება |
| GET | `/purchase-orders/{id}/three-way-match` | `get_three_way_match` | სამმხრივი შეჯერება |
| GET | `/purchase-orders/{id}/workflow` | `get_purchase_workflow` | ნაკადის სტატუსი |
| GET | `/purchase-orders/approval-limits` | `get_approval_limit_info` | დამტკიცების ლიმიტები |

### ხარისხის კონტროლი (`quality_control.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/quality-control/` | `list_quality_checks` |
| GET | `/quality-control/{check_id}` | `get_quality_check` |
| POST | `/quality-control/` | `create_quality_check` |
| PUT | `/quality-control/{check_id}` | `update_quality_check` |
| DELETE | `/quality-control/{check_id}` | `delete_quality_check` |

### დამტკიცების პოლიტიკა (`purchase_approvals.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/purchase-approval-policy/` | `get_purchase_approval_policy` |
| PATCH | `/purchase-approval-policy/` | `update_purchase_approval_policy` |

### შესყიდვის ფასების ისტორია (`purchase_costs.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/purchase-cost-history/` | `list_purchase_cost_history` |

## Frontend API ზარები

- `purchaseOrdersApi.list({search})` → GET `/purchase-orders/`
- `purchaseOrdersApi.get(id)` → GET `/purchase-orders/{id}`
- `purchaseOrdersApi.create(payload)` → POST `/purchase-orders/`
- `suppliersApi.list({page_size: 100})` — მომწოდებლები
- `warehousesApi.list()` — საწყობები
- `productsApi.list({page_size: 100})` — პროდუქტები

## ბიზნეს ლოგიკა

- **ნაკადი:** draft → pending_approval → approved → goods_receipt → quality_check → invoice → paid
- **სამმხრივი შეჯერება:** PO თანხა vs მიღებული რაოდენობა vs ინვოისის თანხა — სხვაობისას გაფრთხილება
- **დამტკიცების ლიმიტები:** თანხის მიხედვით სხვადასხვა როლის დამტკიცება
- **მიღება:** ზრდის მარაგს საწყობში (inventory_balances)
- **ხარისხის შემოწმება:** passed/failed/partial — failed-ზე მიღება ჩერდება

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
