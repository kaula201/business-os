# მოდული: WMS (საწყობის მართვა)

**კოდი:** `wms`
**Route:** `/wms`
**კატეგორია:** operations
**დამოკიდებულია:** `inventory`
**გვერდი:** `frontend/src/pages/WmsPage.tsx` (872 სტრიქონი)
**Backend:** `wms.py`, `wms_ops.py`

---

## მიზანი

საწყობის მოწინავე მართვა: პარტიები (batches), სერიული ნომრები, პიკინგი, შევსება (replenishment), ლენდედ ქოსთი, ლოკაციები, ინვენტარიზაცია, FIFO/FEFO.

## გვერდის სტრუქტურა

### 1. ტაბები

| ტაბი | ფუნქცია |
|------|----------|
| „პარტიები" | პარტიების მართვა |
| „სერიული ნომრები" | სერიული ნომრების მართვა |
| „პიკინგი" | შეკვეთების კომპლექტაცია |
| „შევსება" | მარაგის ავტომატური შევსება |
| „ლენდედ ქოსთი" | დამატებითი ხარჯების განაწილება |
| „ლოკაციები" | საწყობის ლოკაციები |
| „ინვენტარიზაცია" | ინვენტარიზაცია |

### 2. პარტიები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი პარტია" | ღილაკი | შექმნა (`POST /wms/batches`) |
| „FIFO/FEFO" | ღილაკი | გაცემის სტრატეგიის არჩევა |
| „ძიება" | input | ბარკოდით ძებნა (`productsApi.list({barcode})`) |
| „დასრულება" | ღილაკი | პიკინგის დასრულება |

## API Endpoints

### პარტიები და სერიული ნომრები (`wms.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| POST | `/wms/batches` | `create_batch` |
| GET | `/wms/batches` | `list_batches` |
| POST | `/wms/batches/{id}/receive` | `receive_batch` — მიღება |
| POST | `/wms/batches/{id}/adjust` | `adjust_batch` — კორექტირება |
| POST | `/wms/batches/{id}/transfer` | `transfer_batch` — გადატანა |
| POST | `/wms/serials` | `register_serial` |
| GET | `/wms/serials` | `list_serials` |
| PATCH | `/wms/serials/{id}/status` | `update_serial_status` |

### ოპერაციები (`wms_ops.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| POST | `/wms-ops/pick-lists` | `create_pick_list` — პიკინგის სია |
| GET | `/wms-ops/pick-lists` | `list_pick_lists` |
| POST | `/wms-ops/pick-lists/{id}/pick` | `pick_item` — პიკინგი |
| POST | `/wms-ops/pick-lists/{id}/complete` | `complete_pick_list` |
| POST | `/wms-ops/packing-slips` | `create_packing_slip` |
| GET | `/wms-ops/packing-slips` | `list_packing_slips` |
| POST | `/wms-ops/replenishment-rules` | `create_replenishment_rule` |
| GET | `/wms-ops/replenishment-rules` | `list_replenishment_rules` |
| GET | `/wms-ops/replenishment/suggestions` | `replenishment_suggestions` |
| POST | `/wms-ops/landed-costs` | `create_landed_cost` |
| GET | `/wms-ops/landed-costs` | `list_landed_costs` |
| POST | `/wms-ops/landed-costs/{id}/allocate` | `allocate_landed_cost` |
| GET | `/wms-ops/trace/{batch_id}` | `batch_trace` — პარტიის ტრეისინგი |
| GET | `/wms-ops/trace/serial/{serial_id}` | `serial_trace` |
| GET | `/wms-ops/allocation/{product_id}` | `allocation_suggestion` |

## ბიზნეს ლოგიკა

- **FIFO/FEFO:** გაცემის სტრატეგია — პირველი შემოსული/პირველი გასული, ან ვადის მიხედვით
- **ლენდედ ქოსთი:** ტრანსპორტირების/საბაჟოს ხარჯები ნაწილდება პარტიის ერთეულებზე
- **ტრეისინგი:** პარტიის/სერიული ნომრის სრული ისტორია (მიღება → გაყიდვა)
- **შევსება:** წესები განსაზღვრავს მინიმალურ მარაგს და ავტომატურად გვთავაზობს შევსებას

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
