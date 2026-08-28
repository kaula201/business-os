# მოდული: Integrations (ინტეგრაციები)

**კოდი:** `integrations`
**Route:** `/integrations`
**კატეგორია:** operations
**დამოკიდებულია:** `settings`
**გვერდი:** `frontend/src/pages/IntegrationsPage.tsx` (252 სტრიქონი)
**Backend:** `integrations.py`, `api_keys.py`

---

## მიზანი

გარე ინტეგრაციების მართვა: RS.ge (საგადასახადო), API Keys, Webhooks, ბოტ მომხმარებლები.

## გვერდის სტრუქტურა

### 1. RS.ge ინტეგრაცია

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| სტატუსი | ინფორმაცია | `GET /integrations/rs/status` |
| ინვოისის გაგზავნა | ღილაკი | `POST /integrations/rs/invoices/submit` |
| ზედნადების გაგზავნა | ღილაკი | `POST /integrations/rs/waybills/submit` |
| დეკლარაციის ექსპორტი | ღილაკი | `POST /integrations/rs/declarations/export` |

### 2. API Keys

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი API Key" | ღილაკი | შექმნა |
| „შექმნა" | ღილაკი | დადასტურება |

### 3. Webhooks

- სია, შექმნა, წაშლა, მოვლენების ისტორია, წარუმატებელის retry

## API Endpoints

### RS.ge (`integrations.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/integrations/rs/status` | `rs_status` |
| GET | `/integrations/rs/waybills/{waybill_number}` | `get_rs_waybill` |
| POST | `/integrations/rs/invoices/submit` | `submit_invoice` |
| POST | `/integrations/rs/waybills/submit` | `submit_waybill` |
| POST | `/integrations/rs/declarations/export` | `export_declaration` |

### API Keys

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/integrations/api-keys` | `list_api_keys` |
| POST | `/integrations/api-keys` | `create_api_key` |
| DELETE | `/integrations/api-keys/{key_id}` | `delete_api_key` |
| GET | `/api-keys/` | `list_api_keys` |
| POST | `/api-keys/` | `create_api_key` |
| POST | `/api-keys/{key_id}/rotate` | `rotate_api_key` |
| POST | `/api-keys/{key_id}/revoke` | `revoke_api_key` |
| POST | `/api-keys/bot-users` | `create_bot_user` |

### Webhooks

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/integrations/webhooks` | `list_webhooks` |
| POST | `/integrations/webhooks` | `create_webhook` |
| DELETE | `/integrations/webhooks/{id}` | `delete_webhook` |
| GET | `/integrations/webhook-events` | `list_webhook_events` |
| POST | `/integrations/webhook-events/retry` | `retry_failed_events` |
| GET | `/integrations/public/status` | `public_status` |

## ბიზნეს ლოგიკა

- **RS.ge:** ინვოისების/ზედნადების გაგზავნა საგადასახადო სისტემაში (`rs_ge.py` სერვისი)
- **Webhooks:** მოვლენების გაგზავნა გარე სისტემებში, წარუმატებელის retry
- **API Keys:** გარე სისტემების წვდომა API-ზე, rotate/revoke

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
