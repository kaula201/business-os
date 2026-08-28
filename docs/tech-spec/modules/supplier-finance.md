# მოდული: SupplierFinance (მომწოდებლის ფინანსები)

**კოდი:** `supplier-finance`
**Route:** `/supplier-finance`
**კატეგორია:** purchases
**დამოკიდებულია:** `suppliers`
**გვერდი:** `frontend/src/pages/SupplierFinancePage.tsx` (481 სტრიქონი)
**Backend:** `supplier_finance.py`

---

## მიზანი

მომწოდებლის ინვოისების და დავალიანებების (payables) მართვა: ინვოისის შექმნა, დამტკიცება, payable-ის შექმნა, გადახდა, კრედიტ-ნოტა, ზედმეტად გადახდის (overpayment) მართვა.

## გვერდის სტრუქტურა

### 1. ტაბები

| ტაბი | ფუნქცია |
|------|----------|
| „მომწოდებლის ინვოისები" | ინვოისების სია |
| „დავალიანებები" | payables-ის სია |

### 2. ინვოისები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი მომწოდებლის ინვოისი" | ღილაკი | შექმნის ფორმა |
| „დამტკიცება და payable-ის შექმნა" | ღილაკი | ინვოისის დამტკიცება → დავალიანება |
| „საკრედიტო ჩანაწერი" | ღილაკი | კრედიტ-ნოტის შექმნა |
| „გადახდის დაფიქსირება" | ღილაკი | გადახდის შეტანა |
| „გადახდა" | ღილაკი | payable-ზე გადახდა |

### 3. ფორმა

| ველი | ტიპი | წყარო |
|------|------|-------|
| მომწოდებელი | select | `suppliersApi.list({page_size: 100})` |
| შეკვეთა | select | `purchaseOrdersApi.list({page_size: 100})` |
| თანხა | input | |
| დღგ | input | |
| თარიღი | input (date) | |

## API Endpoints

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/supplier-invoices/` | `list_supplier_invoices` | ინვოისების სია |
| POST | `/supplier-invoices/` | `create_supplier_invoice` | შექმნა |
| GET | `/supplier-invoices/{invoice_id}` | `get_supplier_invoice` | ერთი ინვოისი |
| PATCH | `/supplier-invoices/{invoice_id}/status` | `change_supplier_invoice_status` | სტატუსის ცვლილება |
| POST | `/supplier-invoices/check-duplicate` | `check_duplicate_invoice_endpoint` | დუბლიკატის შემოწმება |
| GET | `/supplier-payables/` | `list_supplier_payables` | დავალიანებები |
| GET | `/supplier-payables/{payable_id}` | `get_supplier_payable` | ერთი დავალიანება |
| POST | `/supplier-payables/{payable_id}/payments` | `post_supplier_payment` | გადახდა |
| POST | `/supplier-payables/{payable_id}/credit-notes` | `post_supplier_credit_note` | კრედიტ-ნოტა |
| POST | `/supplier-payments/{payment_id}/reversal` | `reverse_supplier_payment` | გადახდის გაუქმება |
| GET | `/supplier-invoice-tolerances/` | `get_supplier_invoice_tolerances` | ტოლერანტობები |
| PUT | `/supplier-invoice-tolerances/` | `update_supplier_invoice_tolerances` | |
| POST | `/supplier-overpayments/apply` | `apply_overpayment` | ზედმეტი გადახდის გამოყენება |
| GET | `/supplier-overpayments/` | `list_supplier_overpayments` | |

## ბიზნეს ლოგიკა

- **დამტკიცება:** ინვოისის დამტკიცება ქმნის payable-ს (დავალიანებას) და GL გატარებას (ხარჯი/COGS + დღგ)
- **COGS:** მომწოდებლის ინვოისის დამტკიცება არის COGS-ის წყარო (შესყიდვაზე დაფუძნებული)
- **ტოლერანტობები:** ინვოისის vs PO-ს სხვაობის დასაშვები ზღვარი
- **Overpayment:** ზედმეტად გადახდილი თანხა ინახება და გამოიყენება შემდეგ ინვოისზე
- **დუბლიკატების კონტროლი:** იგივე ნომრის/თანხის ინვოისის ხელახლა შეტანის ბლოკირება

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
