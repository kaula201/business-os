# მოდული: Marketplace (აპლიკაციების მარკეტი)

**კოდი:** `marketplace`
**Route:** `/marketplace`
**კატეგორია:** other
**გვერდი:** არ არის ცალკე გვერდი (ახალი, განვითარებაშია)
**Backend:** `marketplace.py`

---

## მიზანი

აპლიკაციების მარკეტი — მზა აპლიკაციების კატალოგი, რომლის ინსტალაცია/დეინსტალაცია შესაძლებელია კომპანიაში (Odoo-ს სტილის app store).

## სტრუქტურა

### 1. აპლიკაციების კატალოგი

- `GET /marketplace/apps` — ხელმისაწვდომი აპლიკაციების სია
- `GET /marketplace/apps/{app_id}` — ერთი აპლიკაციის დეტალები

### 2. ინსტალაცია/დეინსტალაცია

- `POST /marketplace/apps/{app_id}/install` — აპლიკაციის ინსტალაცია
- `POST /marketplace/apps/{app_id}/uninstall` — დეინსტალაცია

### 3. კონფიგურაცია

- `PATCH /marketplace/apps/{app_id}/config` — აპლიკაციის კონფიგურაცია
- `GET /marketplace/my-apps` — დაყენებული აპლიკაციები

## API Endpoints

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/marketplace/apps` | `list_apps` | კატალოგი |
| GET | `/marketplace/apps/{app_id}` | `get_app` | დეტალები |
| POST | `/marketplace/apps` | `create_app` | აპლიკაციის დამატება (ადმინი) |
| POST | `/marketplace/apps/{app_id}/install` | `install_app` | ინსტალაცია |
| POST | `/marketplace/apps/{app_id}/uninstall` | `uninstall_app` | დეინსტალაცია |
| PATCH | `/marketplace/apps/{app_id}/config` | `update_app_config` | კონფიგურაცია |
| GET | `/marketplace/my-apps` | `list_my_apps` | დაყენებული აპლიკაციები |

## ბიზნეს ლოგიკა

- ინსტალაცია აქტიურებს აპლიკაციას კომპანიისთვის (მოდულების სისტემასთან ინტეგრაცია)
- **სტატუსი:** ახალი მოდული — ჯერ არ არის დაკომიტებული და seed-ში არ არის

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
