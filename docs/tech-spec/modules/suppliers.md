# მოდული: Suppliers (მომწოდებლები)

**კოდი:** `suppliers`
**Route:** `/suppliers`
**კატეგორია:** purchases
**გვერდი:** `frontend/src/pages/SuppliersPage.tsx` (209 სტრიქონი)
**Backend:** `suppliers.py`

---

## მიზანი

მომწოდებლების რეესტრი: კომპანიის მონაცემები, საბანკო რეკვიზიტები, რეიტინგები, დუბლიკატების კონტროლი.

## გვერდის სტრუქტურა

### 1. სიის ხედი

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| ძებნა | input | `suppliersApi.list({search})` |
| „ახალი მომწოდებელი" | ღილაკი | შექმნის ფორმა |
| მომწოდებლის რიგი | ცხრილი | სახელი, საიდენტიფიკაციო კოდი, ტელეფონი, სტატუსი |

### 2. ფორმა

| ველი | ტიპი | შენიშვნა |
|------|------|----------|
| სახელი | input | სავალდებულო |
| საიდენტიფიკაციო კოდი | input | უნიკალური, დუბლიკატის შემოწმება |
| დღგ-ს სტატუსი | select | |
| მისამართი | input | |
| ტელეფონი | input | |
| ელ.ფოსტა | input | |

| ღილაკი | ფუნქცია |
|--------|----------|
| „ინახება..." | შენახვა (create/update) |
| „გაუქმება" | ფორმის დახურვა |

## API Endpoints

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/suppliers/` | `list_suppliers` | სია |
| POST | `/suppliers/` | `create_supplier` | შექმნა |
| GET | `/suppliers/{supplier_id}` | `get_supplier` | ერთი მომწოდებელი |
| PATCH | `/suppliers/{supplier_id}` | `update_supplier` | განახლება |
| POST | `/suppliers/{supplier_id}/archive` | `archive_supplier` | არქივირება |
| GET | `/suppliers/check-duplicate-tax-id` | `check_duplicate_tax_id` | დუბლიკატის შემოწმება |
| GET | `/suppliers/{supplier_id}/bank-details` | `list_supplier_bank_details` | საბანკო რეკვიზიტები |
| POST | `/suppliers/{supplier_id}/bank-details` | `create_supplier_bank_detail` | |
| PATCH | `/suppliers/{supplier_id}/bank-details/{id}` | `update_supplier_bank_detail` | |
| DELETE | `/suppliers/{supplier_id}/bank-details/{id}` | `delete_supplier_bank_detail` | |
| POST | `/suppliers/{supplier_id}/ratings` | `rate_supplier` | რეიტინგი |
| GET | `/suppliers/{supplier_id}/ratings` | `list_supplier_ratings` | |
| POST | `/suppliers/seed-demo` | `seed_demo_suppliers` | დემო მონაცემები |

## Frontend API ზარები

- `suppliersApi.list({search})` → GET `/suppliers/`
- `suppliersApi.create(form)` → POST `/suppliers/`
- `suppliersApi.update(id, form)` → PATCH `/suppliers/{id}`

## ბიზნეს ლოგიკა

- **დუბლიკატების კონტროლი:** საიდენტიფიკაციო კოდის შემოწმება შექმნამდე
- **არქივირება:** არქივირებული მომწოდებელი არ ჩანს აქტიურ სიაში, მაგრამ ისტორია რჩება
- **რეიტინგები:** მომწოდებლის შეფასება (დროულობა, ხარისხი, ფასი)
- **საბანკო რეკვიზიტები:** გადახდებისთვის საჭირო მონაცემები

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
