# მოდული: Quotations (კომერციული შემოთავაზებები)

**კოდი:** `quotations`
**Route:** `/quotations`
**კატეგორია:** sales
**დამოკიდებულია:** `clients`
**გვერდი:** `frontend/src/pages/QuotationsPage.tsx` (251 სტრიქონი)
**Backend:** `quotations.py`

---

## მიზანი

კომერციული შემოთავაზებების (quote) შექმნა და მართვა — კლიენტს ეგზავნება ფასების წინადადება, რომელიც შემდეგ შეკვეთად გარდაიქმნება.

## გვერდის სტრუქტურა

### 1. სიის ხედი

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი შემოთავაზება" | ღილაკი | შექმნის ფორმა |
| შემოთავაზების რიგი | ცხრილი | ნომერი, კლიენტი, თარიღი, თანხა, სტატუსი |

### 2. შექმნის ფორმა

| ველი | ტიპი | წყარო |
|------|------|-------|
| კლიენტი | select | `clientsApi.list({page_size: 100})` |
| პროდუქტი | select | `productsApi.list({page_size: 100})` |
| რაოდენობა | input | |
| ფასი | input | |

| ღილაკი | ფუნქცია |
|--------|----------|
| „სტრიქონის დამატება" | პოზიციის დამატება |
| „შენახვა" | შემოთავაზების შენახვა |

## API Endpoints

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/quotations/` | `list_quotations` | სია |
| POST | `/quotations/` | `create_quotation` | შექმნა |
| GET | `/quotations/{quotation_id}` | `get_quotation` | ერთი შემოთავაზება |
| PATCH | `/quotations/{quotation_id}/status` | `update_quotation_status` | სტატუსის ცვლილება |
| POST | `/quotations/{quotation_id}/convert` | `convert_quotation_to_order` | შეკვეთად გადაქცევა |
| DELETE | `/quotations/{quotation_id}` | `delete_quotation` | წაშლა |

## ბიზნეს ლოგიკა

- **კონვერტაცია:** დამტკიცებული შემოთავაზება გარდაიქმნება გაყიდვის შეკვეთად (`convert_quotation_to_order`)
- **სტატუსები:** draft → sent → accepted → converted / rejected

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
