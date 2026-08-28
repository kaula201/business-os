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
| 8 | documents | დოკუმენტები | operations | /documents | [აღწერა](modules/documents.md) |
| 9 | production | წარმოება | operations | /production | [აღწერა](modules/production.md) |
| 10 | projects | პროექტები | operations | /projects | [აღწერა](modules/projects.md) |
| 11 | kitchen | სამზარეულო (KDS) | operations | /kitchen | [აღწერა](modules/kitchen.md) |
| 12 | purchases | შესყიდვები | purchases | /purchases | [აღწერა](modules/purchases.md) |
| 13 | suppliers | მომწოდებლები | purchases | /suppliers | [აღწერა](modules/suppliers.md) |
| 14 | supplier-finance | მომწოდებლის ფინანსები | purchases | /supplier-finance | [აღწერა](modules/supplier-finance.md) |
| 15 | cash | სალარო | finance | /cash | [აღწერა](modules/cash.md) |
| 16 | banking | საბანკო | finance | /banking | [აღწერა](modules/banking.md) |
| 17 | currency | ვალუტის კურსები | finance | /currency | [აღწერა](modules/currency.md) |
| 18 | customer-finance | კლიენტის ფინანსები | finance | /customer-finance | [აღწერა](modules/customer-finance.md) |
| 19 | expenses | ხარჯები | finance | /expenses | [აღწერა](modules/expenses.md) |
| 20 | assets | ძირითადი საშუალებები | finance | /assets | [აღწერა](modules/assets.md) |
| 21 | gl | ანგარიშთა გეგმა | accounting | /chart-of-accounts | [აღწერა](modules/gl.md) |
| 22 | journal-entries | საჟურნალო ჩანაწერები | accounting | /journal-entries | [აღწერა](modules/journal-entries.md) |
| 23 | trial-balance | საცდელი ბალანსი | accounting | /trial-balance | [აღწერა](modules/trial-balance.md) |
| 24 | profit-loss | მოგება-ზარალი | accounting | /profit-loss | [აღწერა](modules/profit-loss.md) |
| 25 | balance-sheet | ბალანსი | accounting | /balance-sheet | [აღწერა](modules/balance-sheet.md) |
| 26 | srs | SRS ანგარიშგება | accounting | /srs | [აღწერა](modules/srs.md) |
| 27 | budgeting | ბიუჯეტირება | accounting | /budgeting | [აღწერა](modules/budgeting.md) |
| 28 | analytic | ანალიტიკური აღრიცხვა | accounting | /analytic-accounting | [აღწერა](modules/analytic.md) |
| 29 | deferred | გადავადებული ოპერაციები | accounting | /deferred | [აღწერა](modules/deferred.md) |
| 30 | accounting-periods | სააღრიცხვო პერიოდები | accounting | /accounting-periods | [აღწერა](modules/accounting-periods.md) |
| 31 | gl-recurring | განმეორებადი ჩანაწერები | accounting | /gl-recurring | [აღწერა](modules/gl-recurring.md) |
| 32 | exchange-differences | საკურსო სხვაობები | accounting | /gl-exchange-differences | [აღწერა](modules/exchange-differences.md) |
| 33 | consolidated | კონსოლიდირებული ანგარიშები | accounting | /gl-consolidated | [აღწერა](modules/consolidated.md) |
| 34 | banking-rules | შეჯერების წესები | finance | /banking-rules | [აღწერა](modules/banking-rules.md) |
| 35 | inventory-valuation | მარაგების შეფასება | operations | /inventory-valuation | [აღწერა](modules/inventory-valuation.md) |
| 36 | quotations | კომერციული შემოთავაზებები | sales | /quotations | [აღწერა](modules/quotations.md) |
| 37 | price-lists | ფასების სიები | sales | /price-lists | [აღწერა](modules/price-lists.md) |
| 38 | sales-teams | გაყიდვების გუნდები | sales | /sales-teams | [აღწერა](modules/sales-teams.md) |
| 39 | email-tracking | ელ.ფოსტა და ხელმოწერები | sales | /email-tracking | [აღწერა](modules/email-tracking.md) |
| 40 | subscriptions | გამოწერები | sales | /subscriptions | [აღწერა](modules/subscriptions.md) |
| 41 | customer-portal | კლიენტის პორტალი | sales | /customer-portal | [აღწერა](modules/customer-portal.md) |
| 42 | vendor-portal | მომწოდებლის პორტალი | purchases | /vendor-portal | [აღწერა](modules/vendor-portal.md) |
| 43 | wms | საწყობის მართვა (WMS) | operations | /wms | [აღწერა](modules/wms.md) |
| 44 | helpdesk | Helpdesk / მხარდაჭერა | operations | /helpdesk | [აღწერა](modules/helpdesk.md) |
| 45 | integrations | ინტეგრაციები | operations | /integrations | [აღწერა](modules/integrations.md) |
| 46 | payments | გადახდები | operations | /payments | [აღწერა](modules/payments.md) |
| 47 | email-calendar | ელ.ფოსტა და კალენდარი | operations | /email-calendar | [აღწერა](modules/email-calendar.md) |
| 48 | security | უსაფრთხოება | operations | /security | [აღწერა](modules/security.md) |
| 49 | automations | ავტომატიზაცია | operations | /automations | [აღწერა](modules/automations.md) |
| 50 | accounting-controls | ბუღალტრული კონტროლები | accounting | /accounting-controls | [აღწერა](modules/accounting-controls.md) |
| 51 | procurement | შესყიდვები — Procurement | purchases | /procurement | [აღწერა](modules/procurement.md) |
| 52 | pos | სალარო (POS) | sales | /pos | [აღწერა](modules/pos.md) |
| 53 | hr | HR / ადამიანური რესურსები | other | /hr | [აღწერა](modules/hr.md) |
| 54 | fleet | ავტოპარკი | fleet | /fleet | [აღწერა](modules/fleet.md) |
| 55 | reports | რეპორტები | other | /reports | [აღწერა](modules/reports.md) |
| 56 | ai | AI ასისტენტი | other | /ai | [აღწერა](modules/ai.md) |
| 57 | settings | პარამეტრები | other | /settings | [აღწერა](modules/settings.md) |
| 58 | ecommerce | ელექტრონული კომერცია | sales | /ecommerce | [აღწერა](modules/ecommerce.md) |
| 59 | plm | პროდუქტის სასიცოცხლო ციკლი | operations | /plm | [აღწერა](modules/plm.md) |
| 60 | notifications | შეტყობინებები | operations | /notifications | [აღწერა](modules/notifications.md) |
| 61 | live-chat | ცოცხალი ჩატი | operations | /live-chat | [აღწერა](modules/live-chat.md) |
| 62 | maintenance | მოვლა-შეკეთება | operations | /maintenance | [აღწერა](modules/maintenance.md) |
| 63 | bank-batch | ბანკის პარტიული დამუშავება | finance | /banking | [აღწერა](modules/bank-batch.md) |
| 64 | financial-automation | ფინანსური ავტომატიზაცია | accounting | /gl/automation | [აღწერა](modules/financial-automation.md) |
| 65 | data-exchange | მონაცემთა ექსპორტი/იმპორტი | operations | /exports | [აღწერა](modules/data-exchange.md) |
| 66 | studio | აპლიკაციების სტუდია | other | /studio | [აღწერა](modules/studio.md) |
| 67 | marketplace | აპლიკაციების მარკეტი | other | /marketplace | [აღწერა](modules/marketplace.md) |

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
2. შედეგს ინახავს `docs/tech-spec/_scan/` საქაღალდეში (pages.json, endpoints.json, summary.json)
3. **git post-commit hook** (`.git/hooks/post-commit`) — ყოველი კომიტის შემდეგ ამოწმებს კოდის ცვლილებას და ავტომატურად აახლებს სკანის მონაცემებს
4. **Cron job** (`tech-spec-auto-update`, ყოველ დილის 6:00) — დუბლირებული შემოწმება, თუ hook რაიმე მიზეზით არ გაეშვა
5. ცვლილებისას იგზავნება შეტყობინება და განახლდება შესაბამისი მოდულის აღწერა

> **შენიშვნა:** `_scan/` მონაცემები ავტომატურად განახლდება, მაგრამ მოდულის `.md` აღწერა (მაგ. ახალი ღილაკის დამატება) ხელით უნდა ჩაემატოს — სკანერი იძლევა ზუსტ მონაცემებს, აღწერას კი ადამიანი/ასისტენტი წერს.

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | დოკუმენტის შექმნა — 53 მოდულის ინდექსი |
| 2026-08-28 | ყველა 67 მოდულის დეტალური აღწერა (5000+ სტრიქონი) + ავტო-განახლება (post-commit hook + cron) |
