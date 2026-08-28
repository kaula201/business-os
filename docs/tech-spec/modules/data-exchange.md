# მოდული: DataExchange (მონაცემთა ექსპორტი/იმპორტი)

**კოდი:** `data-exchange`
**Route:** `/exports`, `/import`, `/export`
**კატეგორია:** operations
**გვერდი:** არ არის ცალკე გვერდი (ღილაკები მოდულებში)
**Backend:** `exports.py`, `import_data.py`, `export.py`

---

## მიზანი

მონაცემთა ზოგადი ექსპორტი/იმპორტი: კლიენტები, პროდუქტები, შეკვეთები, დავალებები — Excel/CSV ფორმატებში.

## API Endpoints

### ექსპორტი (`exports.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/exports/orders` | `export_orders` |
| GET | `/exports/clients` | `export_clients` |
| GET | `/exports/products` | `export_products` |
| GET | `/exports/tasks` | `export_tasks` |

### ექსპორტი (`export.py` — ძველი ვერსია)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/export/clients` | `download_clients` |
| GET | `/export/products` | `download_products` |
| GET | `/export/orders` | `download_orders` |
| GET | `/export/tasks` | `download_tasks` |

### იმპორტი (`import_data.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| POST | `/import/clients` | `import_clients` — კლიენტების იმპორტი |
| POST | `/import/products` | `import_products` — პროდუქტების იმპორტი |

## ბიზნეს ლოგიკა

- ექსპორტი ქმნის Excel ფაილს და აბრუნებს ჩამოსატვირთად
- იმპორტი კითხულობს ფაილს და ქმნის/აახლებს ჩანაწერებს
- გამოიყენება მოდულების ღილაკებიდან („Excel იმპორტი", „Excel ექსპორტი")

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
