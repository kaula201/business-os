# მოდული: VendorPortal (მომწოდებლის პორტალი)

**კოდი:** `vendor-portal`
**Route:** `/vendor-portal`
**კატეგორია:** purchases
**დამოკიდებულია:** `suppliers`
**გვერდი:** `frontend/src/pages/VendorPortalPage.tsx` (230 სტრიქონი)
**Backend:** `vendor_portal.py`, `vendor_auth.py`

---

## მიზანი

მომწოდებლის პორტალის მომხმარებლების მართვა — მომწოდებლებს ეძლევათ წვდომა პორტალზე (შეკვეთები, ინვოისები, გადახდები).

## გვერდის სტრუქტურა

### 1. სიის ხედი

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი პორტალის მომხმარებელი" | ღილაკი | შექმნის ფორმა |
| მომხმარებლის რიგი | ცხრილი | მომწოდებელი, ელ.ფოსტა, სტატუსი |

### 2. ფორმა

| ველი | ტიპი | წყარო |
|------|------|-------|
| მომწოდებელი | select | `suppliersApi.list({page_size: 100})` |
| ელ.ფოსტა | input | |
| სტატუსი | select | active / disabled |

| ღილაკი | ფუნქცია |
|--------|----------|
| „შენახვა" | მომხმარებლის შენახვა (`vendorPortalApi.create`) |

## API Endpoints

### პორტალის მომხმარებლები (`vendor_portal.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/vendor-portal/` | `list_vendor_portal_users` |
| GET | `/vendor-portal/{portal_user_id}` | `get_vendor_portal_user` |
| POST | `/vendor-portal/` | `create_vendor_portal_user` |
| PATCH | `/vendor-portal/{portal_user_id}` | `update_vendor_portal_user` |
| DELETE | `/vendor-portal/{portal_user_id}` | `delete_vendor_portal_user` |
| GET | `/vendor-portal/suppliers/{supplier_id}/summary` | `supplier_summary` |

### ავტორიზაცია (`vendor_auth.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| POST | `/vendor-auth/login` | `vendor_login` — მომწოდებლის შესვლა |
| GET | `/vendor-auth/me` | `vendor_me` |
| GET | `/vendor-auth/dashboard` | `vendor_dashboard` |

## Frontend API ზარები

- `vendorPortalApi.list({page_size: 100})` → GET `/vendor-portal/`
- `vendorPortalApi.create({supplier_id, ...})` → POST `/vendor-portal/`
- `vendorPortalApi.remove(id)` → DELETE `/vendor-portal/{id}`
- `suppliersApi.list({page_size: 100})` — მომწოდებლები

## ბიზნეს ლოგიკა

- პორტალის მომხმარებელი უკავშირდება მომწოდებელს
- მომწოდებელი შედის ცალკე გვერდით: `/vendor/login` → `/vendor/dashboard`
- `supplier_summary` აბრუნებს მომწოდებლის მონაცემებს პორტალისთვის (შეკვეთები, ნაშთი)

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
