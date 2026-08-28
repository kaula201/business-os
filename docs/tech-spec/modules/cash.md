# მოდული: Cash (სალარო)

**კოდი:** `cash`
**Route:** `/cash`
**კატეგორია:** finance
**გვერდი:** `frontend/src/pages/CashPage.tsx` (440 სტრიქონი)
**Backend:** `cash.py`

---

## მიზანი

სალაროს ანგარიშების და ნაღდი ფულის ოპერაციების მართვა: შეტანა, ამოღება, დღიური ანგარიში.

## გვერდის სტრუქტურა

### 1. სალაროს ანგარიშები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „სალაროს შექმნა" | ღილაკი | ახალი სალაროს ანგარიში |
| ანგარიშის ბარათი | ბარათი | სახელი, ნაშთი, ვალუტა |
| რედაქტირება | ღილაკი | ანგარიშის ჩასწორება |
| წაშლა | ღილაკი | ანგარიშის წაშლა |

### 2. ოპერაციები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ოპერაცია" | ღილაკი | ახალი ოპერაცია (შეტანა/ამოღება) |
| ოპერაციების სია | ცხრილი | თარიღი, ტიპი, თანხა, კომენტარი |
| „იქმნება..." | ღილაკი | ოპერაციის შექმნა |
| „ინახება..." | ღილაკი | ანგარიშის შენახვა |

### 3. დღიური ანგარიში

- `GET /cash/accounts/{id}/daily-report` — დღის შემოსავლები/ხარჯები

## API Endpoints

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/cash/accounts` | `list_cash_accounts` | სალაროს ანგარიშები |
| POST | `/cash/accounts` | `create_cash_account` | შექმნა |
| PUT | `/cash/accounts/{account_id}` | `update_cash_account` | განახლება |
| DELETE | `/cash/accounts/{account_id}` | `delete_cash_account` | წაშლა |
| GET | `/cash/accounts/{account_id}/transactions` | `list_cash_transactions` | ოპერაციები |
| POST | `/cash/accounts/{account_id}/transactions` | `create_cash_transaction` | ახალი ოპერაცია |
| GET | `/cash/accounts/{account_id}/daily-report` | `cash_daily_report` | დღიური ანგარიში |

## Frontend API ზარები

- `GET /cash/accounts` — ანგარიშების სია
- `GET /cash/accounts/${id}/transactions` — ოპერაციები
- `GET /cash/accounts/${id}/daily-report` — დღიური ანგარიში
- `POST /cash/accounts` — შექმნა
- `PUT /cash/accounts/${id}` — განახლება
- `DELETE /cash/accounts/${id}` — წაშლა
- `POST /cash/accounts/${id}/transactions` — ოპერაცია

## ბიზნეს ლოგიკა

- ნაღდი ფულის ოპერაციები უკავშირდება GL-ს (სალაროს ანგარიშთა გეგმაში)
- დღიური ანგარიში აჯამებს დღის შემოსავლებსა და ხარჯებს

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
