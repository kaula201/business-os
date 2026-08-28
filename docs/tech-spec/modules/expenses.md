# მოდული: Expenses (ხარჯები)

**კოდი:** `expenses`
**Route:** `/expenses`
**კატეგორია:** finance
**გვერდი:** `frontend/src/pages/ExpensesPage.tsx` (282 სტრიქონი)
**Backend:** `expenses.py`

---

## მიზანი

ხარჯების აღრიცხვა და დამტკიცება: კატეგორიები, ხარჯის ჩანაწერები, დამტკიცების/უარყოფის ნაკადი.

## გვერდის სტრუქტურა

### 1. ხარჯების სია

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი ხარჯი" | ღილაკი | შექმნის ფორმა |
| ხარჯის რიგი | ცხრილი | თარიღი, კატეგორია, თანხა, სტატუსი |

### 2. ფორმა

| ველი | ტიპი | წყარო |
|------|------|-------|
| კატეგორია | select | `GET /expenses/categories` |
| თარიღი | input (date) | |
| თანხა | input | |
| აღწერა | input | |

| ღილაკი | ფუნქცია |
|--------|----------|
| „ინახება..." | შენახვა (create/update) |
| „გაუქმება" | ფორმის დახურვა |

### 3. დამტკიცება

- დამტკიცება: `POST /expenses/{id}/approve`
- უარყოფა: `POST /expenses/{id}/reject`

## API Endpoints

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/expenses/categories` | `list_categories` | კატეგორიები |
| POST | `/expenses/categories` | `create_category` | ახალი კატეგორია |
| GET | `/expenses/` | `list_expenses` | ხარჯების სია |
| POST | `/expenses/` | `create_expense` | შექმნა |
| PUT | `/expenses/{expense_id}` | `update_expense` | განახლება |
| POST | `/expenses/{expense_id}/approve` | `approve_expense` | დამტკიცება |
| POST | `/expenses/{expense_id}/reject` | `reject_expense` | უარყოფა |

## ბიზნეს ლოგიკა

- **დამტკიცების ნაკადი:** draft → pending → approved / rejected
- დამტკიცებული ხარჯი ქმნის GL გატარებას (ხარჯის ანგარიშზე)

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
