# მოდული: Production (წარმოება)

**კოდი:** `production`
**Route:** `/production`
**კატეგორია:** operations
**გვერდი:** `frontend/src/pages/ProductionPage.tsx` (148 სტრიქონი)
**Backend:** `production.py`

---

## მიზანი

წარმოების მართვა: BOM (Bill of Materials), სამუშაო ცენტრები, წარმოების დავალებები (work orders), კომპონენტების ხელმისაწვდომობა, მზა პროდუქციის მიღება.

## გვერდის სტრუქტურა

### 1. BOM (მასალების სია)

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი BOM" | ღილაკი | BOM-ის შექმნა (`POST /production/boms`) |
| „ინახება..." | ღილაკი | BOM-ის შენახვა |
| BOM-ის რიგი | ცხრილი | პროდუქტი, კომპონენტები, ღირებულება |

### 2. წარმოების დავალებები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი წარმოების დავალება" | ღილაკი | შექმნა (`POST /production/work-orders`) |
| „ინახება..." | ღილაკი | დავალების შენახვა |
| დავალების რიგი | ცხრილი | პროდუქტი, რაოდენობა, სტატუსი, ვადა |

## API Endpoints

### BOM

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/production/boms` | `list_boms` | BOM-ების სია |
| POST | `/production/boms` | `create_bom` | შექმნა |
| GET | `/production/boms/{bom_id}` | `get_bom` | ერთი BOM |
| GET | `/production/boms/{bom_id}/cost` | `calculate_bom_cost` | ღირებულების გაანგარიშება |
| GET | `/production/boms/{bom_id}/items` | `list_bom_items` | კომპონენტები |
| POST | `/production/boms/{bom_id}/items` | `add_bom_item` | კომპონენტის დამატება |

### სამუშაო ცენტრები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/production/work-centers` | `list_work_centers` |
| POST | `/production/work-centers` | `create_work_center` |

### წარმოების დავალებები

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/production/work-orders` | `list_work_orders` | დავალებები |
| POST | `/production/work-orders` | `create_work_order` | შექმნა |
| GET | `/production/work-orders/{wo_id}` | `get_work_order` | |
| PATCH | `/production/work-orders/{wo_id}` | `update_work_order` | |
| GET | `/production/work-orders/{wo_id}/availability` | `check_component_availability` | კომპონენტების ხელმისაწვდომობა |
| GET | `/production/work-orders/{wo_id}/reservations` | `list_reservations` | მარაგის რეზერვაცია |
| POST | `/production/work-orders/{wo_id}/reservations` | `create_reservation` | |
| GET | `/production/work-orders/{wo_id}/receipts` | `list_receipts` | მზა პროდუქციის მიღება |
| POST | `/production/work-orders/{wo_id}/receipts` | `create_finished_goods_receipt` | |
| POST | `/production/demo/workflow` | `production_workflow_demo` | დემო ნაკადი |

## ბიზნეს ლოგიკა

- **BOM:** პროდუქტი + კომპონენტები (რაოდენობები) → ღირებულების გაანგარიშება
- **წარმოების დავალება:** BOM-ზე დაფუძნებული, ამოწმებს კომპონენტების ხელმისაწვდომობას
- **რეზერვაცია:** კომპონენტები ირეზერვება მარაგიდან დავალების დაწყებისას
- **მზა პროდუქციის მიღება:** ზრდის მარაგს მზა პროდუქტზე, აკლებს კომპონენტებს

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
