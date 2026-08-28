# მოდული: Automations (ავტომატიზაცია)

**კოდი:** `automations`
**Route:** `/automations`
**კატეგორია:** operations
**დამოკიდებულია:** `settings`
**გვერდი:** `frontend/src/pages/AutomationsPage.tsx` (127 სტრიქონი)
**Backend:** `automations.py`

---

## მიზანი

Trigger → Action ავტომატიზაციის წესები: მოვლენის დადგომისას (მაგ. ინვოისის დადასტურება) ავტომატურად სრულდება მოქმედება (მაგ. შეტყობინება, დავალების შექმნა, ელ.ფოსტა).

## გვერდის სტრუქტურა

### 1. წესების სია

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი წესი" | ღილაკი | შექმნის ფორმა |
| წესის რიგი | ცხრილი | ტრიგერი, მოქმედება, აქტიური/არააქტიური |
| აქტივობის ინდიკატორი | ხატულა | მწვანე = აქტიური |

### 2. წესის ფორმა

| ველი | ტიპი | შესაძლო მნიშვნელობები |
|------|------|------------------------|
| ტრიგერი | select | invoice_issued, order_created, payment_received, ... |
| მოქმედება | select | notify, create_task, send_email, ... |
| სამიზნე როლი | select | manager / admin / accountant |
| პირობები | input | დამატებითი ფილტრები |

## API Endpoints

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/automations/` | `list_rules` | წესების სია |
| POST | `/automations/` | `create_rule` | წესის შექმნა |
| PATCH | `/automations/{rule_id}` | `update_rule` | წესის განახლება |
| DELETE | `/automations/{rule_id}` | `delete_rule` | წესის წაშლა |
| POST | `/automations/trigger/{trigger}` | `run_trigger` | ტრიგერის ხელით გაშვება |

## Frontend API ზარები

- `automationsApi.list()` → GET `/automations/`
- `automationsApi.create(form)` → POST `/automations/`
- `automationsApi.update(id)` → PATCH `/automations/{id}`
- `automationsApi.remove(id)` → DELETE `/automations/{id}`

## ბიზნეს ლოგიკა

- **ტრიგერები:** სისტემის მოვლენები (ინვოისი, შეკვეთა, გადახდა, დავალება)
- **მოქმედებები:** შეტყობინება, დავალების შექმნა, ელ.ფოსტის გაგზავნა
- **პირობები:** ტრიგერი მუშაობს მხოლოდ პირობის დაკმაყოფილებისას
- `run_trigger` საშუალებას აძლევს ტრიგერის ხელით გაშვებას ტესტირებისთვის

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
