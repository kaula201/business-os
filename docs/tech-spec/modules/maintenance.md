# მოდული: Maintenance (მოვლა-შეკეთება)

**კოდი:** `maintenance`
**Route:** `/maintenance`
**კატეგორია:** operations
**გვერდი:** არ არის ცალკე გვერდი (API-ზე დაფუძნებული)
**Backend:** `maintenance.py`

---

## მიზანი

აღჭურვილობის მოვლა-შეკეთების მართვა: პრევენციული მოვლის გეგმები (plans), სამუშაო დავალებები (orders), შეკეთებები (repairs).

## სტრუქტურა

### 1. მოვლის გეგმები (Plans)

- პრევენციული მოვლის გრაფიკები (პერიოდულობა, აღჭურვილობა)

### 2. სამუშაო დავალებები (Orders)

- მოვლის/შეკეთების დავალებები, სტატუსის ცვლილება

### 3. შეკეთებები (Repairs)

- შეკეთების ჩანაწერები, განახლება

## API Endpoints

### გეგმები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/maintenance/plans` | `list_plans` |
| POST | `/maintenance/plans` | `create_plan` |

### დავალებები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/maintenance/orders` | `list_orders` |
| POST | `/maintenance/orders` | `create_order` |
| PATCH | `/maintenance/orders/{order_id}` | `update_order` |

### შეკეთებები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/maintenance/repairs` | `list_repairs` |
| POST | `/maintenance/repairs` | `create_repair` |
| PATCH | `/maintenance/repairs/{repair_id}` | `update_repair` |

## ბიზნეს ლოგიკა

- გეგმა ქმნის დავალებებს პერიოდულად (პრევენციული მოვლა)
- დავალება შეიძლება გადაიზარდოს შეკეთებაში (გაუმართაობისას)

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
