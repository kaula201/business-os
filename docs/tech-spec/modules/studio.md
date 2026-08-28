# მოდული: Studio (აპლიკაციების სტუდია)

**კოდი:** `studio`
**Route:** `/studio`
**კატეგორია:** other
**გვერდი:** არ არის ცალკე გვერდი (ახალი, განვითარებაშია)
**Backend:** `studio.py`

---

## მიზანი

აპლიკაციების სტუდია — მომხმარებლის მიერ შექმნილი აპლიკაციები და ფორმები (no-code მიდგომა): აპლიკაცია → ფორმები → ჩანაწერები.

## სტრუქტურა

### 1. აპლიკაციები (Apps)

- აპლიკაციის შექმნა, განახლება, წაშლა, სია

### 2. ფორმები (Forms)

- აპლიკაციაში ფორმების შექმნა (ველების სტრუქტურა)

### 3. ჩანაწერები (Records)

- ფორმაში მონაცემების შეყვანა, სია, წაშლა

## API Endpoints

### აპლიკაციები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/studio/apps` | `list_studio_apps` |
| POST | `/studio/apps` | `create_studio_app` |
| PATCH | `/studio/apps/{app_id}` | `update_studio_app` |
| DELETE | `/studio/apps/{app_id}` | `delete_studio_app` |

### ფორმები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/studio/apps/{app_id}/forms` | `list_studio_forms` |
| POST | `/studio/apps/{app_id}/forms` | `create_studio_form` |
| DELETE | `/studio/forms/{form_id}` | `delete_studio_form` |

### ჩანაწერები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/studio/forms/{form_id}/records` | `list_studio_records` |
| POST | `/studio/forms/{form_id}/records` | `create_studio_record` |
| DELETE | `/studio/records/{record_id}` | `delete_studio_record` |

## ბიზნეს ლოგიკა

- **No-code:** მომხმარებელი ქმნის აპლიკაციას ფორმებით კოდის გარეშე
- ჩანაწერები ინახება დინამიკურ სტრუქტურაში
- **სტატუსი:** ახალი მოდული — ჯერ არ არის დაკომიტებული და seed-ში არ არის

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
