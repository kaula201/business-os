# მოდული: Banking (საბანკო)

**კოდი:** `banking`
**Route:** `/banking`
**კატეგორია:** finance
**გვერდი:** `frontend/src/pages/BankingPage.tsx` (342 სტრიქონი)
**Backend:** `banking.py`, `bank_rules.py`

---

## მიზანი

საბანკო ანგარიშების მართვა, ამონაწერების (statement) იმპორტი, ტრანზაქციების შეჯერება (reconciliation) და შეჯერების ავტომატური წესები.

## გვერდის სტრუქტურა

### 1. ანგარიშები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ანგარიშის დამატება" | ღილაკი | ახალი საბანკო ანგარიში |
| ანგარიშის ბარათი | ბარათი | ბანკი, ნომერი, ნაშთი |

### 2. ტრანზაქციები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „CSV იმპორტი" | ღილაკი | ამონაწერის იმპორტი (`import_bank_statement`) |
| „ყველას დამტკიცება" | ღილაკი | ყველა ტრანზაქციის დამტკიცება |
| „შეჯერება" | ღილაკი | ტრანზაქციის შეჯერება (`reconcile_bank_transaction`) |
| ტრანზაქციების სია | ცხრილი | თარიღი, აღწერა, თანხა, სტატუსი |

### 3. შეჯერების წინადადებები

- `GET /reconciliation-suggestions` — ავტომატური წინადადებები შეჯერებისთვის

## API Endpoints

### ანგარიშები და ტრანზაქციები (`banking.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/bank-accounts/` | `list_bank_accounts` |
| GET | `/bank-accounts/{id}/balance` | `bank_account_balance` |
| POST | `/bank-accounts/` | `create_bank_account` |
| POST | `/bank-accounts/{id}/statement-imports` | `import_bank_statement` — CSV იმპორტი |
| GET | `/bank-transactions/` | `list_bank_transactions` |
| GET | `/reconciliation-suggestions` | `reconciliation_suggestions` |
| POST | `/bank-transactions/{id}/reconciliations` | `reconcile_bank_transaction` |
| GET | `/bank-reconciliations/` | `list_bank_reconciliations` |
| POST | `/bank-reconciliations/{id}/reversal` | `reverse_bank_reconciliation` — შეჯერების გაუქმება |

### კავშირები (Open Banking)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/connections` | `list_connections` |
| POST | `/connections` | `create_connection` |
| DELETE | `/connections/{id}` | `delete_connection` |
| POST | `/connections/{id}/sync` | `sync_connection` — სინქრონიზაცია |

### შეჯერების წესები (`bank_rules.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/banking/reconciliation-rules/` | `list_rules` |
| POST | `/banking/reconciliation-rules/` | `create_rule` |
| PATCH | `/banking/reconciliation-rules/{id}` | `update_rule` |
| DELETE | `/banking/reconciliation-rules/{id}` | `delete_rule` |
| POST | `/banking/reconciliation-rules/apply` | `apply_all_rules` — ყველა წესის გამოყენება |

## ბიზნეს ლოგიკა

- **შეჯერება:** ბანკის ტრანზაქცია უკავშირდება შიდა ჩანაწერს (ინვოისი, გადახდა)
- **წესები:** ავტომატური შეჯერება წესებით (მაგ. აღწერაში ფრაზის შედარება)
- **Reversal:** შეჯერების გაუქმება შეცდომის შემთხვევაში

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
