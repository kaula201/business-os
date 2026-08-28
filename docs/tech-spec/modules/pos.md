# მოდული: POS (სალარო)

**კოდი:** `pos`
**Route:** `/pos`
**კატეგორია:** sales
**დამოკიდებულია:** `inventory`
**გვერდი:** `frontend/src/pages/PosPage.tsx` (1328 სტრიქონი)
**Backend:** `pos.py`, `pos_hardware.py`, `pos_restaurant.py`

---

## მიზანი

სალაროს (Point of Sale) სრული მართვა: ცვლები, ჩეკები, გადახდები, ფისკალური მოწყობილობები, სასაჩუქრე ბარათები, ლოიალობა, offline რეჟიმი, რესტორნის მაგიდები.

## გვერდის სტრუქტურა

### 1. ზედა ზოლი — ტაბები

| ტაბი | ფუნქცია |
|------|----------|
| „სალარო" | მთავარი სამუშაო ეკრანი |
| „მაგიდები" | რესტორნის მაგიდების მართვა |
| „ფისკალური მოწყობილობები" | პრინტერების/ტერმინალების მართვა |
| „ფისკალური ჟურნალი" | ფისკალური ოპერაციების ისტორია |
| „სასაჩუქრე ბარათები" | Gift card-ების მართვა |
| „Offline" | offline რეჟიმის სტატუსი |

### 2. ცვლა (Shift)

| ღილაკი | ფუნქცია |
|--------|----------|
| „ცვლის გახსნა" | ახალი ცვლის დაწყება (`POST /pos/sessions`) |
| „ცვლის დახურვა" | ცვლის დახურვა (`POST /pos/sessions/{id}/close`) |
| „X-ანგარიში" | შუალედური ანგარიში (`GET /pos/sessions/{id}/x-report`) |
| „Z-ანგარიში და დახურვა" | საბოლოო ანგარიში + დახურვა (`POST /pos/sessions/{id}/z-report`) |
| „შეტანა" | ფულის შეტანა სალაროში (`cash-in`) |
| „ამოღება" | ფულის ამოღება სალაროდან (`cash-out`) |

### 3. გაყიდვის ეკრანი

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| პროდუქტის ძებნა | input | `productsApi.list({page_size: 200})` |
| კლიენტის არჩევა | select | `clientsApi.list({page_size: 200})` |
| ვალუტა | select | GEL / USD / EUR |
| გადახდის ტიპი | select | cash / card / gift_card |
| „დამატება" | ღილაკი | პროდუქტის კალათაში დამატება |
| „გასუფთავება" | ღილაკი | კალათის გასუფთავება |
| „გადახდა და ჩეკი" | ღილაკი | გადახდა + ჩეკის ბეჭდვა |
| „ბოლო ჩეკის ბეჭდვა" | ღილაკი | ბოლო ჩეკის ხელახლა ბეჭდვა |
| „სრული დაბრუნება" | ღილაკი | შეკვეთის სრული დაბრუნება (`refund`) |
| „გადახდა ტერმინალით" | ღილაკი | ტერმინალით გადახდა |
| „QR გადახდა" | ღილაკი | QR კოდით გადახდა (`POST /pos/qr/pay`) |
| „გაგზავნა" | ღილაკი | ჩეკის ელ.ფოსტით გაგზავნა (`email-receipt`) |

### 4. მაგიდები (რესტორნის რეჟიმი)

| ღილაკი | ფუნქცია |
|--------|----------|
| „დაკავება" | მაგიდის დაკავება (`occupy_table`) |
| „გათავისუფლება" | მაგიდის გათავისუფლება (`free_table`) |
| „ნაწილის დამატება" | შეკვეთის დამატება მაგიდაზე |
| „გაყოფა" | ანგარიშის გაყოფა (`split_bill`) |
| „დადასტურება" | შეკვეთის დადასტურება |

### 5. სასაჩუქრე ბარათები

| ღილაკი | ფუნქცია |
|--------|----------|
| „ბარათის გაცემა" | ახალი ბარათი (`POST /pos/gift-cards`) |
| „შეტანა" | ბალანსის შევსება (`top-up`) |
| „დაბლოკვა" | ბარათის დაბლოკვა |
| „ბარათის გაუქმება" | ბარათის გაუქმება (`void`) |
| „ბარათის გახსნა" | ბარათის დეტალები |

### 6. ფისკალური მოწყობილობები

| ღილაკი | ფუნქცია |
|--------|----------|
| „რეგისტრაცია" | ახალი მოწყობილობის რეგისტრაცია |
| „დეაქტივაცია" | მოწყობილობის დეაქტივაცია |
| „სინქრონიზაცია" | მოწყობილობებთან სინქრონიზაცია |
| „PIN-ით შესვლა" | Cashier-ის PIN დადასტურება (`verify_cashier_pin`) |

## API Endpoints

### ცვლები და შეკვეთები (`pos.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/pos/sessions` | `list_sessions` — ცვლების სია |
| POST | `/pos/sessions` | `open_session` — ცვლის გახსნა |
| POST | `/pos/sessions/{id}/close` | `close_session` — ცვლის დახურვა |
| GET | `/pos/orders` | `list_pos_orders` |
| POST | `/pos/orders` | `create_pos_order` — გაყიდვა |
| POST | `/pos/orders/{id}/refund` | `refund_pos_order` — დაბრუნება |
| GET | `/pos/refunds` | `list_refunds` |
| POST | `/pos/orders/{id}/email-receipt` | `email_receipt` — ჩეკი მეილზე |
| POST | `/pos/orders/{id}/split` | `split_bill` — ანგარიშის გაყოფა |
| GET | `/pos/orders/{id}/escpos` | `escpos_receipt` — ESC/POS ჩეკი |
| POST | `/pos/orders/{id}/print` | `print_receipt` — ბეჭდვა |

### ლოიალობა

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/pos/loyalty/{client_id}` | `loyalty_balance` |
| POST | `/pos/loyalty/earn` | `earn_loyalty_points` |
| POST | `/pos/loyalty/redeem` | `redeem_loyalty_points` |

### Offline

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| POST | `/pos/offline/queue` | `queue_offline_order` — offline შეკვეთის რიგში დაყენება |
| GET | `/pos/offline/queue` | `list_offline_queue` |
| POST | `/pos/offline/queue/{id}/sync` | `sync_offline_order` — სინქრონიზაცია |

### ფისკალური მოწყობილობები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/pos/fiscal-devices` | `list_fiscal_devices` |
| POST | `/pos/fiscal-devices` | `register_fiscal_device` |
| PATCH | `/pos/fiscal-devices/{id}` | `update_fiscal_device` |
| GET | `/pos/hardware/status` | `hardware_status` |
| GET | `/pos/fiscal-journal` | `fiscal_journal` — ფისკალური ჟურნალი |

### სასაჩუქრე ბარათები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/pos/gift-cards` | `list_gift_cards` |
| POST | `/pos/gift-cards` | `issue_gift_card` |
| POST | `/pos/gift-cards/{id}/top-up` | `top_up_gift_card` |
| POST | `/pos/gift-cards/{id}/redeem` | `redeem_gift_card` |
| PATCH | `/pos/gift-cards/{id}` | `update_gift_card` |
| POST | `/pos/gift-cards/{id}/void` | `void_gift_card` |

### ცვლის ოპერაციები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| POST | `/pos/sessions/{id}/cash-in` | `cash_in` — შეტანა |
| POST | `/pos/sessions/{id}/cash-out` | `cash_out` — ამოღება |
| GET | `/pos/sessions/{id}/x-report` | `x_report` |
| POST | `/pos/sessions/{id}/z-report` | `z_report` |
| GET | `/pos/z-reports` | `list_z_reports` |

### სამზარეულო

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/pos/kitchen/queue` | `kitchen_queue` |
| PATCH | `/pos/orders/{id}/kitchen-status` | `set_kitchen_status` |

### ფასები და კუპონები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/pos/price-lists` | `list_price_lists` |
| POST | `/pos/price-lists` | `set_price_list` |
| DELETE | `/pos/price-lists/{id}` | `delete_price_list` |
| GET | `/pos/coupons` | `list_coupons` |
| POST | `/pos/coupons` | `create_coupon` |
| POST | `/pos/coupons/validate` | `validate_coupon` |

### ტექნიკა (`pos_hardware.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/pos/registers` | `list_registers` |
| POST | `/pos/registers` | `create_register` |
| GET | `/pos/cashiers` | `list_cashiers` |
| POST | `/pos/cashiers` | `create_cashier` |
| POST | `/pos/cashiers/verify` | `verify_cashier_pin` |
| GET | `/pos/terminals` | `list_terminals` |
| POST | `/pos/terminals` | `create_terminal` |
| POST | `/pos/terminals/{id}/charge` | `terminal_charge` |
| GET | `/pos/customer-balance/{client_id}` | `customer_balance` |
| POST | `/pos/customers/{client_id}/deposit` | `customer_deposit` |
| POST | `/pos/qr/pay` | `qr_payment` |

### რესტორნის რეჟიმი (`pos_restaurant.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/pos/tables` | `list_tables` |
| POST | `/pos/tables` | `create_table` |
| POST | `/pos/tables/{id}/occupy` | `occupy_table` |
| POST | `/pos/tables/{id}/free` | `free_table` |
| PATCH | `/pos/tables/{id}/position` | `set_table_position` |
| GET | `/pos/order-types` | `list_order_types` |
| POST | `/pos/order-types` | `create_order_type` |
| POST | `/pos/self-order/start` | `start_self_order` |
| POST | `/pos/self-order/{token}/submit` | `submit_self_order` |

## ბიზნეს ლოგიკა

- **Offline რეჟიმი:** ინტერნეტის გარეშე შეკვეთები რიგდება ლოკალურად და სინქრონიზდება კავშირის აღდგენისას
- **ფისკალიზაცია:** ESC/POS პროტოკოლი, X/Z ანგარიშები, ფისკალური ჟურნალი
- **ლოიალობა:** ქულების დარიცხვა/ჩამოჭრა კლიენტზე
- **გადახდის ტიპები:** cash, card (ტერმინალი), gift_card, QR

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
