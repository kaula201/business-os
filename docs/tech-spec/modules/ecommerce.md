# მოდული: eCommerce (ელექტრონული კომერცია)

**კოდი:** `ecommerce`
**Route:** `/ecommerce`
**კატეგორია:** sales
**გვერდი:** არ არის ცალკე გვერდი (API-ზე დაფუძნებული, storefront გარე საიტზე)
**Backend:** `ecommerce.py`

---

## მიზანი

ელექტრონული კომერციის ფუნქციონალი: eCommerce კატეგორიები, პროდუქტები, საჯარო storefront (ვიტრინა), კალათა (cart), checkout, შეკვეთები.

## სტრუქტურა

### 1. eCommerce კატეგორიები და პროდუქტები (ადმინისტრირება)

- ცალკე კატეგორიების ხე eCommerce-ისთვის (განსხვავებული ძირითადი პროდუქტებისგან)
- eCommerce პროდუქტები: სახელი, ფასი, ფოტო, აღწერა, ხელმისაწვდომობა

### 2. Storefront (საჯარო ვიტრინა)

- `GET /ecommerce/storefront/categories` — საჯარო კატეგორიები (ავტორიზაციის გარეშე)
- `GET /ecommerce/storefront/products` — საჯარო პროდუქტები

### 3. კალათა და checkout

- კალათის შექმნა, პოზიციების დამატება, კალათის ნახვა
- Checkout — კალათიდან შეკვეთის შექმნა

## API Endpoints

### კატეგორიები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/ecommerce/categories` | `list_ecom_categories` |
| POST | `/ecommerce/categories` | `create_ecom_category` |
| PATCH | `/ecommerce/categories/{cat_id}` | `update_ecom_category` |
| DELETE | `/ecommerce/categories/{cat_id}` | `delete_ecom_category` |

### პროდუქტები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/ecommerce/products` | `list_ecom_products` |
| POST | `/ecommerce/products` | `create_ecom_product` |
| PATCH | `/ecommerce/products/{product_id}` | `update_ecom_product` |
| DELETE | `/ecommerce/products/{product_id}` | `delete_ecom_product` |

### Storefront (საჯარო)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/ecommerce/storefront/categories` | `public_categories` |
| GET | `/ecommerce/storefront/products` | `public_products` |

### კალათა და checkout

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| POST | `/ecommerce/cart` | `create_cart` |
| POST | `/ecommerce/cart/{cart_id}/items` | `add_cart_item` |
| GET | `/ecommerce/cart/{cart_id}` | `get_cart` |
| POST | `/ecommerce/cart/{cart_id}/checkout` | `checkout` — შეკვეთის შექმნა |
| GET | `/ecommerce/orders` | `list_orders` — eCommerce შეკვეთები |

## ბიზნეს ლოგიკა

- **Checkout:** კალათა → შეკვეთა (შეკვეთის მოდელზე დაფუძნებული)
- **Storefront:** საჯარო endpoints ავტორიზაციის გარეშე — გარე საიტისთვის
- **კატეგორიები:** ცალკე ხე, არ ერევა ძირითად პროდუქტებს

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
