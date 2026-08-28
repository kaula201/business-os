# მოდული: GL (ანგარიშთა გეგმა)

**კოდი:** `gl`
**Route:** `/chart-of-accounts`
**კატეგორია:** accounting
**გვერდი:** `frontend/src/pages/ChartOfAccountsPage.tsx` (138 სტრიქონი)
**Backend:** `gl.py`, `gl_enhanced.py`

---

## მიზანი

ანგარიშთა გეგმის (Chart of Accounts) მართვა — ყველა ბუღალტრული ანგარიში, მათი ტიპები და სტრუქტურა. ეს არის მთელი ბუღალტერიის საფუძველი.

## გვერდის სტრუქტურა

### 1. ანგარიშების სია

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი ანგარიში" | ღილაკი | შექმნის ფორმა |
| „რედაქტირება" | ღილაკი | არსებული ანგარიშის ჩასწორება |
| ანგარიშის რიგი | ცხრილი | კოდი, სახელი, ტიპი, ვალუტა |

### 2. ფორმა

| ველი | ტიპი | შენიშვნა |
|------|------|----------|
| კოდი | input | უნიკალური |
| სახელი | input | |
| ტიპი | select | აქტივი / ვალდებულება / კაპიტალი / შემოსავალი / ხარჯი |
| მშობელი ანგარიში | select | იერარქია |
| ვალუტა | select | |

## API Endpoints

### ძირითადი (`gl.py`)

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/gl/accounts/` | `list_accounts` | ანგარიშების სია |
| POST | `/gl/accounts/` | `create_account` | შექმნა |
| GET | `/gl/accounts/{account_id}` | `get_account` | ერთი ანგარიში |
| PATCH | `/gl/accounts/{account_id}` | `update_account` | განახლება |
| GET | `/gl/journal-entries/` | `list_journal_entries` | ჟურნალის ჩანაწერები |
| POST | `/gl/journal-entries/` | `create_manual_journal_entry` | ხელით ჩანაწერი |
| GET | `/gl/journal-entries/{entry_id}` | `get_journal_entry` | ერთი ჩანაწერი |
| GET | `/gl/trial-balance/` | `trial_balance` | საცდელი ბალანსი |
| GET | `/gl/profit-loss/` | `profit_loss` | მოგება-ზარალი |
| GET | `/gl/balance-sheet/` | `balance_sheet` | ბალანსი |

### გაფართოებული (`gl_enhanced.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| POST | `/gl/period-close` | `close_accounting_period` — პერიოდის დახურვა |
| GET | `/gl/analytics` | `gl_analytics` — ანალიტიკა |
| GET | `/gl/export/accounts` | `export_chart_of_accounts` — ექსპორტი |
| GET | `/gl/export/journal` | `export_journal_entries` |
| GET | `/gl/export/trial-balance` | `export_trial_balance` |

## ბიზნეს ლოგიკა

- **ანგარიშის ტიპები:** აქტივი, ვალდებულება, კაპიტალი, შემოსავალი, ხარჯი
- **იერარქია:** მშობელი/შვილი ანგარიშები
- ყველა ფინანსური ოპერაცია (ინვოისი, გადახდა, ხარჯი) ქმნის GL ჩანაწერს ამ გეგმის მიხედვით

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
