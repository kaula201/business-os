# მოდული: CustomerPortal (კლიენტის პორტალი)

**კოდი:** `customer-portal`
**Route:** `/customer-portal`
**კატეგორია:** sales
**დამოკიდებულია:** `clients`
**გვერდი:** `frontend/src/pages/PortalPage.tsx` (193 სტრიქონი)
**Backend:** `customer_portal.py`

---

## მიზანი

კლიენტის პორტალის მომხმარებლების მართვა — კლიენტებს ეძლევათ წვდომა პორტალზე (ინვოისები, გადახდები, დოკუმენტები).

## გვერდის სტრუქტურა

### 1. სიის ხედი

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი პორტალის მომხმარებელი" | ღილაკი | შექმნის ფორმა |
| მომხმარებლის რიგი | ცხრილი | კლიენტი, ელ.ფოსტა, სტატუსი |

### 2. შექმნის ფორმა

| ველი | ტიპი | წყარო |
|------|------|-------|
| კლიენტი | select | `clientsApi.list({page_size: 100})` |
| ელ.ფოსტა | input | |
| სტატუსი | select | `active` / `disabled` |

| ღილაკი | ფუნქცია |
|--------|----------|
| „შენახვა" | მომხმარებლის შენახვა |

## API Endpoints

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/customer-portal/` | `list_portal_users` | სია |
| GET | `/customer-portal/{portal_user_id}` | `get_portal_user` | ერთი მომხმარებელი |
| POST | `/customer-portal/` | `create_portal_user` | შექმნა |
| PATCH | `/customer-portal/{portal_user_id}` | `update_portal_user` | განახლება |
| DELETE | `/customer-portal/{portal_user_id}` | `delete_portal_user` | წაშლა |
| GET | `/customer-portal/clients/{client_id}/summary` | `client_portal_summary` | კლიენტის პორტალის შეჯამება |

## ბიზნეს ლოგიკა

- პორტალის მომხმარებელი უკავშირდება კლიენტს
- `client_portal_summary` აბრუნებს კლიენტის მონაცემებს პორტალისთვის (ინვოისები, ნაშთი)

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
