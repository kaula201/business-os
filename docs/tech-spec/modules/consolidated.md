# მოდული: Consolidated (კონსოლიდირებული ანგარიშები)

**კოდი:** `consolidated`
**Route:** `/gl-consolidated`
**კატეგორია:** accounting
**დამოკიდებულია:** `gl`
**გვერდი:** `frontend/src/pages/ConsolidatedReportsPage.tsx` (182 სტრიქონი)
**Backend:** `consolidated.py`, `consolidation_eliminations.py`, `consolidation_purchases.py`

---

## მიზანი

მრავალკომპანიური კონსოლიდირებული ანგარიშები: P&L და ბალანსი რამდენიმე კომპანიის გაერთიანებით, შიდაკომპანიური ოპერაციების ელიმინაციით.

## გვერდის სტრუქტურა

### 1. კომპანიების არჩევა

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| კომპანიების სია | select (multi) | `GET /gl/consolidated/companies` |
| „მუშავდება..." | ღილაკი | ანგარიშის გენერაცია |

### 2. ელიმინაციები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „დადასტურება" | ღილაკი | ელიმინაციის დამტკიცება (`approve_elimination`) |
| „გაუქმება" | ღილაკი | ელიმინაციის გაუქმება (`reverse_elimination`) |

## API Endpoints

### კონსოლიდაცია (`consolidated.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/gl/consolidated/companies` | `consolidated_companies` |
| GET | `/gl/consolidated/profit-loss` | `consolidated_pl` — კონსოლიდირებული P&L |
| GET | `/gl/consolidated/balance-sheet` | `consolidated_bs` — კონსოლიდირებული ბალანსი |

### ელიმინაციები (`consolidation_eliminations.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/gl/consolidation-eliminations/` | `list_eliminations` |
| POST | `/gl/consolidation-eliminations/` | `create_elimination` |
| POST | `/gl/consolidation-eliminations/{id}/approve` | `approve_elimination` |
| POST | `/gl/consolidation-eliminations/{id}/reverse` | `reverse_elimination` |
| POST | `/gl/consolidation-eliminations/auto-detect` | `auto_detect_eliminations` — ავტო აღმოჩენა |
| POST | `/gl/consolidation-eliminations/auto-detect-purchases` | `auto_detect_purchase_eliminations` — შესყიდვების ავტო აღმოჩენა |

## ბიზნეს ლოგიკა

- **ელიმინაცია:** შიდაკომპანიური გაყიდვები/შესყიდვები/დავალიანებები იშლება კონსოლიდაციისას
- **ავტო-აღმოჩენა:** სისტემა პოულობს შესაძლო ელიმინაციებს (იგივე თანხა ორ კომპანიაში)
- ელიმინაცია მოითხოვს დამტკიცებას

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
