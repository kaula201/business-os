# მოდული: CustomerFinance (კლიენტის ფინანსები)

**კოდი:** `customer-finance`
**Route:** `/customer-finance`
**კატეგორია:** finance
**დამოკიდებულია:** `invoices`
**გვერდი:** `frontend/src/pages/CustomerFinancePage.tsx` (249 სტრიქონი)
**Backend:** `customer_finance.py`

---

## მიზანი

მოვალეების (receivables) მართვა: დავალიანებები, გადახდები, კრედიტ-ნოტები, ანგარიშგება (statement), შეჯერება ბანკთან.

## გვერდის სტრუქტურა

### 1. მოვალეების სია

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| სტატუსის ფილტრი | select | unpaid / partially_paid / overdue / paid / credited |
| კლიენტის ფილტრი | select | კლიენტის მიხედვით |
| მოვალის რიგი | ცხრილი | კლიენტი, თანხა, ვადა, სტატუსი |

### 2. მოქმედებები

| ღილაკი | ფუნქცია |
|--------|----------|
| „იქმნება..." | გადახდის შექმნა (`create_payment`) |
| „ინახება..." | კრედიტ-ნოტის შენახვა |
| „მუშავდება..." | შეჯერება/გაუქმება |

## API Endpoints

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/customer-receivables/` | `list_receivables` | მოვალეების სია |
| GET | `/customer-receivables/{id}` | `get_receivable` | ერთი დავალიანება |
| POST | `/customer-receivables/{id}/payments` | `create_payment` | გადახდა |
| POST | `/customer-payments/{id}/reversal` | `reverse_payment` | გადახდის გაუქმება |
| POST | `/customer-receivables/{id}/credit-notes` | `create_credit_note` | კრედიტ-ნოტა |
| POST | `/bank-transactions/{id}/customer-reconciliations` | `reconcile_customer_receivable` | ბანკთან შეჯერება |
| GET | `/customer-receivables/{id}/statement` | `customer_statement` | ანგარიშგება |
| GET | `/bank-customer-reconciliations/` | `list_customer_reconciliations` | შეჯერებების სია |
| POST | `/bank-customer-reconciliations/{id}/reversal` | `reverse_customer_reconciliation` | შეჯერების გაუქმება |

## ბიზნეს ლოგიკა

- **დავალიანება იქმნება ინვოისის დადასტურებისას** (issue)
- **გადახდა:** ამცირებს დავალიანებას და ქმნის GL გატარებას
- **კრედიტ-ნოტა:** აუქმებს/ამცირებს დავალიანებას
- **სტატუსები:** unpaid → partially_paid → paid; overdue ვადის გადაცილებისას

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
