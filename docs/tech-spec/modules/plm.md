# მოდული: PLM (პროდუქტის სასიცოცხლო ციკლი)

**კოდი:** `plm`
**Route:** `/plm`
**კატეგორია:** operations
**დამოკიდებულია:** `products`
**გვერდი:** არ არის ცალკე გვერდი (API-ზე დაფუძნებული)
**Backend:** `plm.py`

---

## მიზანი

პროდუქტის სასიცოცხლო ციკლის მართვა (PLM — Product Lifecycle Management): პროდუქტის ვერსიები, საინჟინრო ცვლილებები (ECO), lifecycle სტადიები.

## სტრუქტურა

### 1. პროდუქტის ვერსიები

- პროდუქტის მონაცემების ვერსიონირება (რევიზიები)
- ვერსიის შექმნა, სია

### 2. საინჟინრო ცვლილებები (ECO — Engineering Change Order)

- ცვლილების მოთხოვნის შექმნა, განახლება, სია
- ცვლილების დამტკიცების ნაკადი

### 3. Lifecycle სტადიები

- პროდუქტის სტადია: development → testing → production → discontinued
- სტადიის ცვლილება

## API Endpoints

### ვერსიები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/plm/products/{product_id}/versions` | `list_versions` |
| POST | `/plm/products/{product_id}/versions` | `create_version` |

### საინჟინრო ცვლილებები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/plm/engineering-changes` | `list_ecos` |
| POST | `/plm/engineering-changes` | `create_eco` |
| PATCH | `/plm/engineering-changes/{eco_id}` | `update_eco` |

### Lifecycle

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/plm/products/{product_id}/lifecycle` | `get_lifecycle` |
| PUT | `/plm/products/{product_id}/lifecycle` | `update_lifecycle` |

## ბიზნეს ლოგიკა

- **ვერსიები:** ყოველი ცვლილება ქმნის ახალ რევიზიას, ისტორია შენარჩუნებულია
- **ECO:** ცვლილების ფორმალური დოკუმენტი — რა იცვლება, რატომ, ვინ ამტკიცებს
- **Lifecycle:** სტადია განსაზღვრავს პროდუქტის ხელმისაწვდომობას (მაგ. discontinued არ იყიდება)

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
