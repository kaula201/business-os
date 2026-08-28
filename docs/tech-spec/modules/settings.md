# მოდული: Settings (პარამეტრები)

**კოდი:** `settings`
**Route:** `/settings`
**კატეგორია:** other
**გვერდი:** `frontend/src/pages/SettingsPage.tsx` (378 სტრიქონი)
**Backend:** `settings_enhanced.py`, `company.py`, `users.py`, `purchase_approvals.py`

---

## მიზანი

კომპანიის პარამეტრები: კომპანიის მონაცემები, მოდულების ჩართვა/გამორთვა, ელ.ფოსტის კონფიგურაცია, მომხმარებლების მართვა, RS.ge სტატუსი, შესყიდვების დამტკიცების ლიმიტები.

## გვერდის სტრუქტურა

### 1. კომპანიის მონაცემები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ინახება..." | ღილაკი | კომპანიის შენახვა (`PATCH /companies/me`) |
| სახელი, კოდი, მისამართი, ტელეფონი | inputs | |

### 2. მოდულები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ინახება..." | ღილაკი | მოდულის ჩართვა/გამორთვა (`POST /settings/modules/toggle`) |
| მოდულების სია | ცხრილი | `GET /settings/modules` |

### 3. ელ.ფოსტის კონფიგურაცია

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „მოწმდება..." | ღილაკი | SMTP კავშირის შემოწმება |
| „ინახება..." | ღილაკი | კონფიგურაციის შენახვა (`POST /settings/email`) |

### 4. მომხმარებლები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „მოწვევა" | ღილაკი | მომხმარებლის მოწვევა (`POST /users/invite`) |
| „იძებნება..." | ღილაკი | ძებნა |
| მომხმარებლების სია | ცხრილი | `usersApi.list({page_size: 100})` |

### 5. RS.ge

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| სტატუსი | ინფორმაცია | `GET /integrations/rs/status` |
| ზედნადის ძებნა | input | `GET /integrations/rs/waybills/{number}` |

### 6. შესყიდვების დამტკიცების ლიმიტები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| ლიმიტები | ცხრილი | `purchaseApprovalApi.get()` |
| „ინახება..." | ღილაკი | ლიმიტის განახლება (`purchaseApprovalApi.update`) |

## API Endpoints

### პარამეტრები (`settings_enhanced.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/settings/system` | `system_info` — სისტემის ინფორმაცია |
| GET | `/settings/modules` | `list_all_modules` |
| POST | `/settings/modules/toggle` | `toggle_module` |
| GET | `/settings/email` | `get_email_config` |
| POST | `/settings/email` | `update_email_config` |

### კომპანია (`company.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/companies/me` | `get_my_company` |
| PATCH | `/companies/me` | `update_my_company` |

### მომხმარებლები (`users.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/users/` | `list_users` |
| GET | `/users/me` | `get_me` |
| GET | `/users/{user_id}` | `get_user` |
| PATCH | `/users/{user_id}` | `update_user` |
| DELETE | `/users/{user_id}` | `deactivate_user` |
| POST | `/users/invite` | `invite_user` — მოწვევა |
| POST | `/users/change-password` | `change_password` |

### დამტკიცების ლიმიტები (`purchase_approvals.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/purchase-approval-policy/` | `get_purchase_approval_policy` |
| PATCH | `/purchase-approval-policy/` | `update_purchase_approval_policy` |

## Frontend API ზარები

- `GET /integrations/rs/status` — RS.ge სტატუსი
- `GET /integrations/rs/waybills/${number}` — ზედნადის ძებნა
- `usersApi.list({page_size: 100})` — მომხმარებლები
- `purchaseApprovalApi.get()` / `.update(limit)` — ლიმიტები

## ბიზნეს ლოგიკა

- **მოდულების მართვა:** კომპანიის დონეზე ჩართვა/გამორთვა ცვლის sidebar-ს და უფლებებს
- **მოწვევა:** მომხმარებლის მოწვევა ელ.ფოსტით (SMTP ან sandbox)
- **დამტკიცების ლიმიტები:** თანხის ზღვარი, რომლის ზემოთაც მენეჯერი ვერ ამტკიცებს შესყიდვას

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
