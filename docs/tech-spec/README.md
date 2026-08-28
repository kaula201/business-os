# Business OS — ტექნიკური დავალება (Tech Spec)

**ვერსია:** 1.0.0
**ბოლო განახლება:** 2026-08-28
**სტატუსი:** აქტიური — ავტომატურად განახლდება კოდის ცვლილებებთან ერთად

---

## როგორ იკითხება ეს დოკუმენტი

ეს არის Business OS-ის სრული ტექნიკური დავალება: თითოეული მოდული, თითოეული გვერდი, თითოეული ღილაკი — რას აკეთებს, რა მონაცემებს აჩვენებს, რომელ API-ს იძახებს.

თითოეული მოდულის დეტალური აღწერა ცალკე ფაილშია: `docs/tech-spec/modules/<code>.md`

## მოდულების სია

| # | კოდი | სახელი | კატეგორია | Route | დეტალები |
|---|------|--------|-----------|-------|----------|
| 1 | dashboard | Dashboard | main | /dashboard | [აღწერა](modules/dashboard.md) |
| 2 | crm | CRM | sales | /crm | [აღწერა](modules/crm.md) |
| 3 | clients | კლიენტების რეესტრი | sales | /clients | [აღწერა](modules/clients.md) |
| 4 | orders | გაყიდვის შეკვეთები | sales | /orders | [აღწერა](modules/orders.md) |
| 5 | invoices | გაყიდვის ინვოისები | sales | /invoices | [აღწერა](modules/invoices.md) |
| 6 | inventory | საწყობი | operations | /inventory | [აღწერა](modules/inventory.md) |
| 7 | tasks | დავალებები | operations | /tasks | [აღწერა](modules/tasks.md) |
| 8 | purchases | შესყიდვები | purchases | /purchases | [აღწერა](modules/purchases.md) |
| 9 | suppliers | მომწოდებლები | purchases | /suppliers | [აღწერა](modules/suppliers.md) |
| 10 | supplier-finance | მომწოდებლის ფინანსები | purchases | /supplier-finance | [აღწერა](modules/supplier-finance.md) |
| 11 | cash | სალარო | finance | /cash | [აღწერა](modules/cash.md) |
| 12 | banking | საბანკო | finance | /banking | [აღწერა](modules/banking.md) |
| 13 | currency | ვალუტის კურსები | finance | /currency | [აღწერა](modules/currency.md) |
| 14 | customer-finance | კლიენტის ფინანსები | finance | /customer-finance | [აღწერა](modules/customer-finance.md) |
| 15 | expenses | ხარჯები | finance | /expenses | [აღწერა](modules/expenses.md) |
| 16 | assets | ძირითადი საშუალებები | finance | /assets | [აღწერა](modules/assets.md) |
| 17 | gl | ანგარიშთა გეგმა | accounting | /chart-of-accounts | [აღწერა](modules/gl.md) |
| 18 | journal-entries | საჟურნალო ჩანაწერები | accounting | /journal-entries | [აღწერა](modules/journal-entries.md) |
| 19 | trial-balance | საცდელი ბალანსი | accounting | /trial-balance | [აღწერა](modules/trial-balance.md) |
| 20 | profit-loss | მოგება-ზარალი | accounting | /profit-loss | [აღწერა](modules/profit-loss.md) |
| 21 | balance-sheet | ბალანსი | accounting | /balance-sheet | [აღწერა](modules/balance-sheet.md) |
| 22 | srs | SRS ანგარიშგება | accounting | /srs | [აღწერა](modules/srs.md) |
| 23 | budgeting | ბიუჯეტირება | accounting | /budgeting | [აღწერა](modules/budgeting.md) |
| 24 | analytic | ანალიტიკური აღრიცხვა | accounting | /analytic-accounting | [აღწერა](modules/analytic.md) |
| 25 | deferred | გადავადებული ოპერაციები | accounting | /deferred | [აღწერა](modules/deferred.md) |
| 26 | accounting-periods | სააღრიცხვო პერიოდები | accounting | /accounting-periods | [აღწერა](modules/accounting-periods.md) |
| 27 | gl-recurring | განმეორებადი ჩანაწერები | accounting | /gl-recurring | [აღწერა](modules/gl-recurring.md) |
| 28 | exchange-differences | საკურსო სხვაობები | accounting | /gl-exchange-differences | [აღწერა](modules/exchange-differences.md) |
| 29 | consolidated | კონსოლიდირებული ანგარიშები | accounting | /gl-consolidated | [აღწერა](modules/consolidated.md) |
| 30 | banking-rules | შეჯერების წესები | finance | /banking-rules | [აღწერა](modules/banking-rules.md) |
| 31 | inventory-valuation | მარაგების შეფასება | operations | /inventory-valuation | [აღწერა](modules/inventory-valuation.md) |
| 32 | quotations | კომერციული შემოთავაზებები | sales | /quotations | [აღწერა](modules/quotations.md) |
| 33 | price-lists | ფასების სიები | sales | /price-lists | [აღწერა](modules/price-lists.md) |
| 34 | sales-teams | გაყიდვების გუნდები | sales | /sales-teams | [აღწერა](modules/sales-teams.md) |
| 35 | email-tracking | ელ.ფოსტა და ხელმოწერები | sales | /email-tracking | [აღწერა](modules/email-tracking.md) |
| 36 | subscriptions | გამოწერები | sales | /subscriptions | [აღწერა](modules/subscriptions.md) |
| 37 | customer-portal | კლიენტის პორტალი | sales | /customer-portal | [აღწერა](modules/customer-portal.md) |
| 38 | vendor-portal | მომწოდებლის პორტალი | purchases | /vendor-portal | [აღწერა](modules/vendor-portal.md) |
| 39 | wms | საწყობის მართვა (WMS) | operations | /wms | [აღწერა](modules/wms.md) |
| 40 | helpdesk | Helpdesk / მხარდაჭერა | operations | /helpdesk | [აღწერა](modules/helpdesk.md) |
| 41 | integrations | ინტეგრაციები | operations | /integrations | [აღწერა](modules/integrations.md) |
| 42 | payments | გადახდები | operations | /payments | [აღწერა](modules/payments.md) |
| 43 | email-calendar | ელ.ფოსტა და კალენდარი | operations | /email-calendar | [აღწერა](modules/email-calendar.md) |
| 44 | security | უსაფრთხოება | operations | /security | [აღწერა](modules/security.md) |
| 45 | automations | ავტომატიზაცია | operations | /automations | [აღწერა](modules/automations.md) |
| 46 | accounting-controls | ბუღალტრული კონტროლები | accounting | /accounting-controls | [აღწერა](modules/accounting-controls.md) |
| 47 | procurement | შესყიდვები — Procurement | purchases | /procurement | [აღწერა](modules/procurement.md) |
| 48 | pos | სალარო (POS) | sales | /pos | [აღწერა](modules/pos.md) |
| 49 | hr | HR / ადამიანური რესურსები | other | /hr | [აღწერა](modules/hr.md) |
| 50 | fleet | ავტოპარკი | fleet | /fleet | [აღწერა](modules/fleet.md) |
| 51 | reports | რეპორტები | other | /reports | [აღწერა](modules/reports.md) |
| 52 | ai | AI ასისტენტი | other | /ai | [აღწერა](modules/ai.md) |
| 53 | settings | პარამეტრები | other | /settings | [აღწერა](modules/settings.md) |

## დამატებითი გვერდები (არა მოდულები)

| Route | გვერდი | აღწერა |
|-------|--------|--------|
| /login | შესვლა | ავტორიზაცია |
| /register | რეგისტრაცია | ახალი კომპანიის რეგისტრაცია |
| /verify-email | ელ.ფოსტის დადასტურება | |
| /vendor/login | მომწოდებლის შესვლა | |
| /vendor/dashboard | მომწოდებლის dashboard | |

## არქიტექტურა

- **Backend:** FastAPI (Python 3.12, async SQLAlchemy, PostgreSQL)
- **Frontend:** React 18 + TypeScript + Vite, TanStack Query, i18next (KA/EN)
- **Auth:** JWT + RBAC (მოდულის დონეზე: can_access / can_create / can_edit / can_delete / can_approve)
- **მოდულების სისტემა:** Odoo-ს სტილის — `app_modules` კატალოგი, `company_modules` ჩართვა/გამორთვა, `module_permissions` როლების უფლებები
- **მონაცემთა ბაზა:** PostgreSQL (Colima/Docker), 75 მოდელი

## სტრუქტურა

```
backend/
  app/
    api/v1/endpoints/   # 98 endpoint ფაილი
    models/              # 75 SQLAlchemy მოდელი
    schemas/             # Pydantic სქემები
    services/            # ბიზნეს ლოგიკა (GL, inventory, email...)
    migrations/          # Alembic
  seed_modules.py        # მოდულების კატალოგი + ნაგულისხმევი უფლებები
  tests/                 # pytest (283 ტესტი)
frontend/
  src/
    pages/               # 62 გვერდი
    components/          # layout, ui, chat
    services/api.ts      # ყველა API კლიენტი
    store/               # Zustand
    i18n.ts              # KA/EN თარგმანები
```

## ავტო-განახლება

ეს დოკუმენტაცია ავტომატურად განახლდება კოდის ცვლილებებისას:

1. `scripts/tech_spec_scan.py` — სკანირებს frontend გვერდებს (ღილაკები, ფილტრები, ცხრილები) და backend endpoints-ებს
2. შედეგს ინახავს `docs/tech-spec/_scan/` საქაღალდეში
3. ცვლილებისას იგზავნება შეტყობინება და განახლდება შესაბამისი მოდულის აღწერა

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | დოკუმენტის შექმნა — 53 მოდულის ინდექსი |
