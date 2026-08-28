# მოდული: Budgeting (ბიუჯეტირება)

**კოდი:** `budgeting`
**Route:** `/budgeting`
**კატეგორია:** accounting
**გვერდი:** `frontend/src/pages/BudgetingPage.tsx` (233 სტრიქონი)
**Backend:** `budgeting.py`

---

## მიზანი

ბიუჯეტის გეგმების მართვა — პერიოდული ბიუჯეტები ანგარიშების მიხედვით, ფაქტობრივი შესრულების შედარებით.

## გვერდის სტრუქტურა

### 1. ბიუჯეტის გეგმები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ბიუჯეტი" | ღილაკი | ახალი გეგმის შექმნა |
| გეგმის რიგი | ცხრილი | სახელი, პერიოდი, თანხა |
| „იქმნება..." | ღილაკი | გეგმის შენახვა |
| „დახურვა" | ღილაკი | ფორმის დახურვა |

### 2. გეგმის ხაზები

- `GET /budgeting/plans/{id}/lines` — ხაზები ანგარიშების მიხედვით
- `GET /budgeting/plans/{id}/period-breakdown` — პერიოდების დაშლა

## API Endpoints

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/budgeting/plans` | `list_plans` | გეგმების სია |
| POST | `/budgeting/plans` | `create_plan` | შექმნა |
| PUT | `/budgeting/plans/{plan_id}` | `update_plan` | განახლება |
| DELETE | `/budgeting/plans/{plan_id}` | `delete_plan` | წაშლა |
| GET | `/budgeting/plans/{plan_id}/lines` | `list_budget_lines` | ხაზები |
| POST | `/budgeting/plans/{plan_id}/lines` | `create_budget_lines` | ხაზების შექმნა |
| GET | `/budgeting/plans/{plan_id}/period-breakdown` | `budget_period_breakdown` | პერიოდების დაშლა |
| GET | `/budgeting/scenarios` | `list_scenarios` | სცენარები |

## ბიზნეს ლოგიკა

- ბიუჯეტის ხაზი: ანგარიში + დაგეგმილი თანხა პერიოდისთვის
- შესრულება ითვლება ფაქტობრივი GL ნაშთებიდან

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
