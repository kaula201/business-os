# Business OS MVP Transformation Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** არსებული CRM/შეკვეთების prototype გარდაიქმნას ქართულ Business Operations OS-ად, რომლის ბირთვია ოპერაციები, ფინანსური კონტროლი, ქართული შესაბამისობა და კონტროლირებადი AI.

**Architecture:** სისტემა რჩება modular monolith-ად FastAPI + React/TypeScript + PostgreSQL სტეკზე. ყველა საოპერაციო დოკუმენტი ქმნის აუდიტირებად მოვლენებს; ფინანსური და საგადასახადო მოქმედებები გადის დამტკიცების პროცესს. გარე ინტეგრაციები გამოიყოფა adapter-ებად, რათა RS.ge, ბანკები და სხვა სისტემები არ შეერიოს domain ლოგიკას.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL 16, React, TypeScript, TanStack Query, Docker/Colima, pytest.

---

## პროდუქტის სამი ფენა

1. **Operations:** კლიენტები, გაყიდვები, შესყიდვები, მრავალსაწყობიანი მარაგები, მიწოდება, ავტოპარკი და დაბრუნებები.
2. **Finance & Georgian Compliance:** ინვოისები, გადახდები, დავალიანებები, საბანკო შეჯერება, RS.ge, საბუღალტრო გატარებები და აუდიტი.
3. **Intelligence & Automation:** ქართულენოვანი AI, გაფრთხილებები, დამტკიცებები, დილის მიმოხილვა და პროგნოზები.

## უცვლელი წესები

- AI ვერ დაადასტურებს გადახდას, RS.ge დოკუმენტს ან საბუღალტრო გატარებას ადამიანის დასტურის გარეშე.
- ყველა ჩანაწერი იზოლირებულია `company_id`-ით.
- ფულადი მნიშვნელობები ახალ მოდულებში ინახება `Numeric/Decimal` ტიპით და არა `Float`-ით.
- მარაგის ცვლილება ხდება მხოლოდ მოძრაობის დოკუმენტით; პირდაპირი ჩასწორება არ არის საბოლოო არქიტექტურა.
- მნიშვნელოვანი ცვლილება ინახავს ავტორს, დროს, მიზეზს და წინა/ახალ მნიშვნელობას.
- გარე ინტეგრაციები არის idempotent და ინახავს მოთხოვნის/პასუხის ტექნიკურ ისტორიას სენსიტიური მონაცემების გარეშე.

## განხორციელების ეტაპები

### მიმდინარე მდგომარეობა — 2026-07-22

დასრულებულია:

- მრავალსაწყობიანი მოდელი, ნაშთები, მიღება/გაცემა/კორექტირება და გადატანა;
- უარყოფითი ნაშთის დაცვა და საწყობის მოძრაობების ისტორია;
- ძველი `current_stock` ნაშთების idempotent გადატანა მთავარ საწყობში;
- დესტრუქციული seed-ის გაუქმება — backend restart მონაცემებს აღარ შლის;
- test database-ის იზოლაცია და 16/16 backend ტესტის წარმატებით გაშვება;
- შეკვეთის async lazy-loading შეცდომის გასწორება;
- Vite-ის TypeScript declaration და წარმატებული production build;
- Docker runtime, API smoke test და ვიზუალური UI შემოწმება.

### P0 stabilization gate — ეტაპი 2-ის დაწყებამდე

პირველი ინკრემენტი დასრულებულია 2026-07-22:

- Client-ის VAT/contact/Interaction კონტრაქტი გასწორდა API-სა და UI ტიპებთან;
- Client create/detail/update და Interaction regression ტესტებით დაფარულია;
- Product categories-ის static route automated test-ით დადასტურდა;
- Order detail UI სრულ detail endpoint-ს იყენებს;
- Order create-ის პროდუქტის lookup `company_id`-ით იზოლირებულია;
- სხვა კომპანიის პროდუქტის გამოყენება იბლოკება და მის ნაშთს არ ცვლის;
- Order dropdown-ების არასწორი `page_size=200` შეიცვალა დაშვებულ 100-ზე;
- სრული backend suite: 19/19; frontend production build: წარმატებული.

Warehouse lifecycle ინკრემენტი დასრულებულია 2026-07-22:

- საწყობის კოდის, სახელისა და მისამართის რედაქტირება;
- სხვა აქტიური საწყობის მთავარ საწყობად მონიშვნა;
- ცარიელი და გამოუყენებელი საწყობის უსაფრთხო hard delete;
- გამოყენებული, მაგრამ განულებული საწყობის დეაქტივაცია ისტორიის შენარჩუნებით;
- ნაშთიანი და მთავარი საწყობის წაშლის/დეაქტივაციის ბლოკირება;
- არქივირებული საწყობების UI-ში ნახვა;
- warehouse create/update/default/archive/delete audit event-ები;
- AuditLog-ის UUID კონტრაქტის გასწორება და model registry-ში დამატება;
- სრული backend suite: 22/22; frontend production build და headless UI შემოწმება წარმატებულია.

Order lifecycle ინკრემენტი დასრულებულია 2026-07-23:

- კონტროლირებადი state machine: `new → confirmed → preparing → shipping → completed`;
- გაუქმება, დაბრუნება და duplicate reversal-ის აკრძალვა;
- warehouse-scoped reservation confirmation-ზე და რეალური issue shipping-ზე;
- concurrent overselling-ის პრევენცია row locking-ით;
- transaction-safe დოკუმენტის ნომერატორი;
- warehouse manual issue/transfer ოპერაციებში დარეზერვებული მარაგის დაცვა;
- immutable movement, history და audit trail;
- lifecycle, reservation და history UI.

Purchase Order და Goods Receipt ინკრემენტი დასრულებულია 2026-07-23:

- tenant-scoped Supplier CRUD, უნიკალური კოდი/საიდენტიფიკაციო ნომერი და დეაქტივაცია;
- Purchase Order: `draft → approved → partially_received → received`, დამატებით `cancelled`;
- `Numeric/Decimal` რაოდენობები, ფასები, ფასდაკლება, დღგ და ჯამები;
- transaction-safe `PO-*` და `GR-*` ნომერატორი;
- partial/final Goods Receipt და over-receipt-ის აკრძალვა;
- receipt idempotency და concurrent receipt-ისგან დაცვა;
- კონკრეტული საწყობის balance-ისა და `Product.current_stock`-ის ერთ transaction-ში ზრდა;
- immutable `purchase_receipt` მოძრაობები, status history და audit trail;
- active Purchase Order-ში გამოყენებული warehouse-ის archive/delete დაცვა;
- მომწოდებლებისა და შესყიდვების UI, approval, receipt form და მიღებების ისტორია;
- purchase integration suite: 5/5; სრული backend suite: 36/36; frontend production build წარმატებულია;
- Docker rebuild/deploy, production schema და live UI API მოთხოვნები დადასტურებულია.

Supplier Invoice და Payable ინკრემენტი დასრულებულია 2026-07-23:

- Supplier Invoice მხოლოდ მიღებულ Purchase Order-ს უკავშირდება;
- `PO ↔ Goods Receipt ↔ Supplier Invoice` 3-way matching ამოწმებს cumulative რაოდენობას, ფასს, ფასდაკლებასა და დღგ-ს;
- mismatch ინახება განმარტებით, მაგრამ ასეთი invoice ვერ მტკიცდება;
- matched invoice-ის approval ერთ transaction-ში ქმნის Supplier Payable-ს;
- payable სტატუსებია `unpaid`, `partially_paid`, `paid` და due date-დან გამოთვლილი `overdue`;
- ნაწილობრივი და სრული გადახდა, payment history და audit trail;
- company-scoped payment idempotency და concurrent overpayment-ის row-lock დაცვა;
- Supplier Invoice/Payable UI, match issue-ები, filter-ები, approval და payment modal;
- Purchase Order-ის დეტალიდან Supplier Invoice-ის პირდაპირი შექმნა;
- finance integration suite: 6/6; სრული backend suite: 42/42; frontend production build წარმატებულია;
- Docker rebuild/deploy, production schema, OpenAPI route-ები და live UI API მოთხოვნები დადასტურებულია.

Costing, Purchase approval და Alembic safety ინკრემენტები დასრულებულია 2026-07-23:

- Goods Receipt transaction-ში weighted-average cost და immutable purchase cost history;
- ფასდაკლების თვითღირებულებაში ჩართვა და recoverable VAT-ის გამორიცხვა;
- Inventory UI-ში average cost, ბოლო შესყიდვის ფასი და Supplier/PO/Receipt traceability;
- company-scoped approval policy: manager თანხის ზღვრამდე, admin ნებისმიერ თანხაზე;
- employee/accountant approval-ის backend აკრძალვა და permission-aware UI;
- admin-only approval threshold Settings UI და audit event;
- destructive `DROP TYPE ... CASCADE` ამოღებულია Alembic runtime-იდან;
- pre-Alembic production schema უსაფრთხოდ adopt/stamp-დება `001_initial` baseline-ზე;
- backend startup იყენებს `python -m app.core.migrate_schema` და შემდეგ `alembic upgrade head`-ს;
- disposable database-ზე bootstrap და განმეორებითი idempotent migration წარმატებულია — 34 table;
- production baseline adoption-ის წინ/შემდეგ row counts და ID checksum-ები უცვლელია;
- costing suite: 2/2; approval suite: 2/2; migration safety suite: 2/2;
- სრული backend suite: 48/48; frontend production build წარმატებულია;
- Docker rebuild/deploy, Alembic startup, OpenAPI routes და error-free runtime logs დადასტურებულია.

Supplier Credit Note და payment reversal ინკრემენტი დასრულებულია 2026-07-23:

- finance-only Supplier Credit Note უკავშირდება original invoice/payable-ს და მარაგს ავტომატურად არ ცვლის;
- `original_amount - paid_amount - credited_amount` არის backend-ის authoritative balance formula;
- partial/full credit, over-credit protection, supplier credit-note number uniqueness და company-scoped idempotency;
- original payment-ზე მიბმული immutable one-time reversal, რომელიც payable balance-ს აღადგენს;
- row locking, Decimal arithmetic, audit events, admin/accountant authorization და tenant isolation;
- Supplier Finance UI-ში credited amount, Credit Note form/history და payment reversal reason/history;
- additive Alembic revision `002_supplier_finance_reversals`, ორი ახალი table და `credited_amount` column;
- targeted finance suite: 5/5; სრული backend suite: 53/53; frontend production build წარმატებულია;
- production row counts უცვლელია; migration revision, 57 OpenAPI route, HTTP 200 და runtime logs დადასტურებულია.

საბანკო ამონაწერის იმპორტისა და reconciliation-ის ინკრემენტი დასრულებულია 2026-07-23:

- tenant-scoped Bank Account create/list და admin/accountant authorization;
- CSV import სავალდებულო სვეტების, თარიღის, Decimal თანხის, direction-ისა და ანგარიშის ვალუტის validation-ით;
- statement-level idempotency, SHA-256 content hash და transaction fingerprint duplicate protection;
- debit transaction-ის ნაწილობრივი/სრული მიბმა Supplier Payable-ზე;
- reconciliation ქმნის immutable Supplier Payment-ს და transaction/payable balances-ს ერთ transaction-ში ცვლის;
- overmatch/overpayment protection, row locking, audit trail და tenant isolation;
- reversal აღადგენს payable balance-სა და bank transaction-ის unmatched თანხას, ისტორიას კი არ შლის;
- Banking UI: ანგარიშები, CSV upload, transaction filters, reconciliation form/history და reversal;
- additive Alembic revision `003_bank_reconciliation`, ოთხი ახალი table და ექვსი ძირითადი unique constraint;
- targeted banking suite: 3/3; სრული backend suite: 56/56; migration safety: 2/2; frontend build წარმატებულია;
- production revision `003_bank_reconciliation`, 63 OpenAPI path, HTTP 200 და authenticated live list checks დადასტურებულია.

Customer Invoice generation ინკრემენტი დასრულებულია 2026-07-23:

- დადასტურებული/მიმდინარე შეკვეთიდან tenant-scoped immutable Invoice snapshot;
- გამყიდველის, მყიდველის, შეკვეთისა და line-item მონაცემები ინახება ცალკე და Order-ის შემდგომი ცვლილება ინვოისს აღარ ცვლის;
- თანხები ინახება `Decimal`/`Numeric` ფორმატით: subtotal, VAT და total;
- company-scoped `INV-*` numbering, idempotency key და ერთ Order-ზე ერთი invoice constraint;
- admin/accountant authorization, cross-tenant protection, Order row lock და same-transaction audit;
- Invoice list/detail API და snapshot-based Georgian PDF download invoice date/due date-ით;
- frontend-ში ცალკე „ინვოისები“ გვერდი, search/detail/PDF და Orders გვერდიდან due date/notes ფორმით გენერირება;
- additive Alembic revision `004_customer_invoicing`, legacy invoice/item backfill და ოთხი unique constraint;
- disposable production clone-ზე `003 → 004` migration: `invoices=1`, `invoice_items=1`, `null_snapshots=0`;
- targeted invoice suite: 4/4; invoice+migration safety: 6/6; სრული backend suite: 60/60; frontend build წარმატებულია;
- production revision `004_customer_invoicing`, 65 OpenAPI path, row counts უცვლელია, authenticated list/detail/PDF და HTTP 200 დადასტურებულია.

შემდეგი სამუშაოა Customer Receivable და Order-to-Cash-ის დასრულება:

1. Invoice approval/issue-დან კლიენტის დებიტორული დავალიანების შექმნა.
2. კლიენტის partial/full payment, reversal და credit note.
3. credit bank transaction-ის Customer Receivable-თან reconciliation.
4. ავტომატური match რეკომენდაციები reference/თანხა/კონტრაგენტის მიხედვით.
5. თითოეული მომდევნო schema ცვლილებისთვის additive Alembic revision.
6. Pydantic/datetime deprecation warnings-ის ეტაპობრივი გასწორება.

P0-ის მიღების კრიტერიუმები:

- Client, Product categories, Order detail და Invoice-ის ძირითადი flow-ები გადის API/UI ტესტებს;
- სხვა კომპანიის entity-ზე წვდომა იბლოკება automated test-ით;
- schema ცვლილება სრულდება Alembic upgrade-ით მონაცემების დაკარგვის გარეშე;
- შეკვეთის, მარაგისა და ინვოისის კრიტიკული ცვლილებები ტოვებს audit trail-ს;
- სრული backend suite და frontend production build წარმატებულია.

### ეტაპი 0: საფუძვლის გამყარება

- Alembic migrations-ის რეალურად ამუშავება.
- დაზიანებული ქართული ტექსტების გასწორება.
- duplicate database/config/export მოდულების გაერთიანება.
- ტესტების იზოლაცია და CI-ready test command.
- საერთო audit event და approval primitives.

### ეტაპი 1: მრავალსაწყობიანი მარაგები — პირველი ვერტიკალური პროცესი

**მიზანი:** პროდუქტი ინახებოდეს ერთ ან მეტ საწყობში, ჩანდეს თითოეული ნაშთი და შესაძლებელი იყოს უსაფრთხო გადატანა.

**Backend ფაილები:**
- Create: `backend/app/models/warehouse.py`
- Create: `backend/app/schemas/warehouse.py`
- Create: `backend/app/api/v1/endpoints/warehouses.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/api/v1/router.py`
- Modify: `backend/app/models/product.py`
- Test: `backend/tests/test_warehouses.py`

**Frontend ფაილები:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/pages/InventoryPage.tsx`

**მიღების კრიტერიუმები:**
- საწყობის შექმნა და სია.
- კომპანიის მონაცემების იზოლაცია.
- პროდუქტის ნაშთი თითო საწყობში.
- მიღება, გაცემა, კორექტირება და საწყობებს შორის გადატანა.
- უარყოფითი ნაშთის აკრძალვა.
- თითო მოძრაობაზე ავტორი, მიზეზი და დრო.
- UI-ში საწყობის არჩევა და გადატანის ფორმა.

### ეტაპი 2: შესყიდვა → მიღება → მომწოდებლის დავალიანება

- Suppliers, PurchaseRequest, PurchaseOrder, GoodsReceipt.
- მიღება ზრდის კონკრეტული საწყობის ნაშთს.
- ფასების ისტორია და `Decimal` თვითღირებულება.
- მიღებული და დაუფარავი თანხის საფუძველზე payable.
- დამტკიცება თანხის ზღვრების მიხედვით.

### ეტაპი 3: გაყიდვა → ინვოისი → დებიტორული დავალიანება

- შეთავაზება, შეკვეთა, ფასდაკლების წესები და დაბრუნება.
- მარაგის რეზერვაცია და გაცემა კონკრეტული საწყობიდან.
- ინვოისი, გადახდის ვადა, ნაწილობრივი გადახდა და overdue მდგომარეობა.
- კლიენტის ისტორია, საკრედიტო ლიმიტი და მარჟა.

### ეტაპი 4: მიწოდება და მძღოლის გარემო

- Delivery, Route, Stop, Vehicle, Driver.
- შეკვეთების მარშრუტში გაერთიანება და ჩატვირთვის კონტროლი.
- მძღოლის responsive/PWA გარემო, offline queue და sync.
- ფოტო/ხელმოწერა/PIN, თანხის მიღება, დაბრუნება და უარის მიზეზი.

### ეტაპი 5: საბანკო ოპერაციები და შეჯერება

- ბანკის ამონაწერის import adapter-ები.
- ტრანზაქციის ინვოისთან დაკავშირება და ნაწილობრივი შეჯერება.
- ვალუტა და ეროვნული ბანკის კურსები.
- ავტომატური match რეკომენდაცია; საბოლოო დადასტურება ადამიანის მიერ.

### ეტაპი 6: RS.ge და ქართული შესაბამისობა

- Waybill/TaxInvoice-ის შიდა canonical მოდელები.
- RS.ge sandbox adapter და sync queue.
- შექმნა, დადასტურება, გაუქმება, კორექტირება.
- სისტემისა და RS.ge მონაცემების შეჯერება და mismatch alerts.
- immutable audit trail.

### ეტაპი 7: ფინანსური ბირთვი

- CashAccount, BankAccount, Payment, JournalEntry, JournalLine.
- დებიტორული/კრედიტორული დავალიანებები.
- შემოსავალი, ხარჯი, მოგება, დღგ და cash flow.
- დახურული პერიოდის ცვლილებების აკრძალვა.

### ეტაპი 8: Intelligence & Automation

- დილის მენეჯერული მიმოხილვა.
- წყაროს მითითებით ქართულენოვანი კითხვა-პასუხი.
- დაბალი ნაშთი, ნელი გაყიდვა, overdue, მიწოდების დაგვიანება და RS.ge mismatch alerts.
- tool/action proposal → approval → execution მოდელი.

### ეტაპი 9: მიგრაცია და ღია ინტეგრაციები

- Excel-ის mapping/import wizard, validation და dry run.
- ძველი სისტემიდან მონაცემების გაწმენდა და reconciliation report.
- versioned public API, webhooks და API keys.
- POS, e-commerce, courier, accounting და Power BI connectors.

## პირველი ეტაპის TDD ნაბიჯები

1. დაწერე API ტესტი საწყობის შექმნა/სიისთვის; გაუშვი და დაადასტურე 404/FAIL.
2. შექმენი Warehouse მოდელი, schema და endpoint; გაუშვი ტესტი PASS-მდე.
3. დაწერე failing ტესტი საწყობის ნაშთის მიღებაზე.
4. შექმენი InventoryBalance და warehouse-aware StockMovement.
5. დაწერე failing ტესტი არასაკმარისი ნაშთით გაცემაზე.
6. დაამატე atomic validation და transaction handling.
7. დაწერე failing ტესტი საწყობებს შორის გადატანაზე.
8. შექმენი წყვილი მოძრაობა ერთი transfer reference-ით.
9. გაუშვი სრული backend test suite.
10. დაამატე frontend types/API/UI, გაუშვი `npm run build`.
11. rebuild Docker და smoke-test რეალური API-ით.
12. ბრაუზერში ვიზუალური შემოწმება desktop და mobile ზომებზე.

## შემდეგი კომერციული დემო

პირველი დემო აჩვენებს ერთიან ციკლს: პროდუქტის მიღება მთავარ საწყობში → ფილიალის საწყობში გადატანა → ნაშთების რეალურ დროში ნახვა → მოძრაობების აუდიტი → დაბალი ნაშთის გაფრთხილება.
