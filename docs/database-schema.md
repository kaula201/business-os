# Business OS — Database Schema
# PostgreSQL + SQLAlchemy (async)

## ERD (Entity Relationship Diagram)

```
┌──────────────────┐       ┌──────────────────┐
│    companies      │       │      users        │
├──────────────────┤       ├──────────────────┤
│ id (PK)          │──┐    │ id (PK)          │
│ name             │  │    │ company_id (FK)  │◄─┐
│ identification_code│ │    │ email            │  │
│ address          │  │    │ hashed_password  │  │
│ phone            │  │    │ full_name        │  │
│ email            │  │    │ role             │  │
│ website          │  │    │ is_active        │  │
│ logo_url         │  │    │ created_at       │  │
│ vat_status       │  │    │ updated_at       │  │
│ currency         │  │    └──────────────────┘  │
│ created_at       │  │                           │
│ updated_at       │  │                           │
└────────┬─────────┘  │                           │
         │            │                           │
         │    ┌───────┘                           │
         │    │                                   │
         ▼    ▼                                   │
┌──────────────────┐                              │
│     clients       │                              │
├──────────────────┤                              │
│ id (PK)          │                              │
│ company_id (FK)  │◄─────────────────────────────┘
│ client_type      │ (იურიდიული/ფიზიკური)
│ name             │
│ identification_code│ (უნიკალური)
│ vat_status       │
│ address          │
│ status           │ (პოტენციური/აქტიური/არააქტიური)
│ notes            │
│ created_by (FK)  │ → users
│ created_at       │
│ updated_at       │
│ deleted_at       │ (soft delete)
└────────┬─────────┘
         │
         │ 1:N
         ▼
┌──────────────────┐
│    contacts       │
├──────────────────┤
│ id (PK)          │
│ client_id (FK)   │
│ full_name        │
│ position         │
│ phone            │
│ email            │
│ is_primary       │
│ created_at       │
└──────────────────┘

┌──────────────────┐       ┌──────────────────┐
│     orders        │       │   order_items     │
├──────────────────┤       ├──────────────────┤
│ id (PK)          │──┐    │ id (PK)          │
│ company_id (FK)  │  │    │ order_id (FK)    │◄─┐
│ client_id (FK)   │  │    │ product_id (FK)  │  │
│ order_number     │  │    │ quantity         │  │
│ status           │  │    │ unit_price       │  │
│ subtotal         │  │    │ discount_percent │  │
│ vat_amount       │  │    │ total            │  │
│ total            │  │    └──────────────────┘  │
│ delivery_date    │  │                           │
│ delivery_address │  │                           │
│ notes            │  │                           │
│ assigned_to (FK) │  │ → users                  │
│ created_by (FK)  │  │ → users                  │
│ created_at       │  │                           │
│ updated_at       │  │                           │
└────────┬─────────┘  │                           │
         │            │                           │
         │            │    ┌──────────────────┐   │
         │            │    │    products       │   │
         │            │    ├──────────────────┤   │
         │            └───►│ id (PK)          │   │
         │                 │ company_id (FK)  │───┘
         │                 │ sku              │
         │                 │ name             │
         │                 │ description      │
         │                 │ category_id (FK) │
         │                 │ sale_price       │
         │                 │ purchase_price   │
         │                 │ unit             │
         │                 │ min_stock        │
         │                 │ current_stock    │
         │                 │ image_url        │
         │                 │ is_active        │
         │                 │ created_at       │
         │                 │ updated_at       │
         │                 └──────────────────┘
         │
         │ 1:N
         ▼
┌──────────────────┐
│  order_status_history │
├──────────────────┤
│ id (PK)          │
│ order_id (FK)    │
│ status           │
│ notes            │
│ changed_by (FK)  │ → users
│ created_at       │
└──────────────────┘

┌──────────────────┐
│      tasks        │
├──────────────────┤
│ id (PK)          │
│ company_id (FK)  │ → companies
│ client_id (FK)   │ → clients (optional)
│ order_id (FK)    │ → orders (optional)
│ title            │
│ description      │
│ status           │ (todo/in_progress/done/cancelled)
│ priority         │ (low/medium/high)
│ due_date         │
│ assigned_to (FK) │ → users
│ created_by (FK)  │ → users
│ created_at       │
│ updated_at       │
└────────┬─────────┘
         │
         │ 1:N
         ▼
┌──────────────────┐
│   task_comments   │
├──────────────────┤
│ id (PK)          │
│ task_id (FK)     │
│ user_id (FK)     │
│ content          │
│ created_at       │
└──────────────────┘

┌──────────────────┐
│ stock_movements   │
├──────────────────┤
│ id (PK)          │
│ product_id (FK)  │
│ movement_type    │ (in/out/adjustment)
│ quantity         │
│ reason           │
│ reference_type   │ (order/adjustment/purchase)
│ reference_id     │
│ created_by (FK)  │ → users
│ created_at       │
└──────────────────┘

┌──────────────────┐
│    categories     │
├──────────────────┤
│ id (PK)          │
│ company_id (FK)  │
│ name             │
│ parent_id (FK)   │ → self (nested)
│ created_at       │
└──────────────────┘

┌──────────────────┐
│ interaction_logs  │
├──────────────────┤
│ id (PK)          │
│ client_id (FK)   │
│ type             │ (note/call/meeting/email)
│ description      │
│ created_by (FK)  │ → users
│ created_at       │
└──────────────────┘

┌──────────────────┐
│   invoices        │
├──────────────────┤
│ id (PK)          │
│ order_id (FK)    │
│ invoice_number   │
│ pdf_url          │
│ created_at       │
└──────────────────┘

┌──────────────────┐
│   audit_logs      │
├──────────────────┤
│ id (PK)          │
│ company_id (FK)  │
│ user_id (FK)     │
│ action           │ (create/update/delete)
│ entity_type      │ (client/order/product/task)
│ entity_id        │
│ old_value        │ (JSON)
│ new_value        │ (JSON)
│ created_at       │
└──────────────────┘
```

## პრინციპები

1. **ყველა ცხრილში** `id UUID PRIMARY KEY` (არა auto-increment)
2. **Soft delete** — `deleted_at TIMESTAMP NULL` (არა ფიზიკური წაშლა)
3. **აუდიტი** — `created_at`, `updated_at` + `audit_logs`
4. **Multi-tenancy** — `company_id` ყველა ცხრილში (row-level)
5. **ქართული მონაცემები** — UTF-8, case-insensitive ძებნა
6. **ინდექსები** — ყველა FK-ზე + ძირითად საძიებო ველებზე
