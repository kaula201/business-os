# მოდული: Documents (დოკუმენტები)

**კოდი:** `documents`
**Route:** `/documents`
**კატეგორია:** operations
**გვერდი:** `frontend/src/pages/DocumentsPage.tsx` (182 სტრიქონი)
**Backend:** `documents.py`

---

## მიზანი

დოკუმენტების მართვა: ატვირთვა, კატეგორიები, ვერსიები, დამტკიცების ნაკადი, გამოქვეყნება, ვადის კონტროლი, აუდიტის ჟურნალი.

## გვერდის სტრუქტურა

### 1. დოკუმენტების სია

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „დოკუმენტის დამატება" | ღილაკი | ატვირთვის ფორმა |
| „ინახება..." | ღილაკი | დოკუმენტის შენახვა |
| დოკუმენტის რიგი | ცხრილი | სახელი, კატეგორია, ვერსია, სტატუსი, ვადა |

### 2. კატეგორიები

- `GET /documents/categories` — კატეგორიების სია
- `GET /documents/categories/tree` — ხის სტრუქტურა

## API Endpoints

### დოკუმენტები

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/documents/upload-policy` | `get_upload_policy` | ატვირთვის პოლიტიკა |
| GET | `/documents/` | `list_documents` | სია |
| POST | `/documents/` | `create_document` | შექმნა/ატვირთვა |
| GET | `/documents/{doc_id}` | `get_document` | ერთი დოკუმენტი |
| PATCH | `/documents/{doc_id}` | `update_document` | განახლება |
| DELETE | `/documents/{doc_id}` | `archive_document` | არქივირება |
| DELETE | `/documents/{doc_id}/permanent` | `permanent_delete_document` | სამუდამო წაშლა |
| GET | `/documents/expired` | `list_expired_documents` | ვადაგასული დოკუმენტები |

### კატეგორიები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/documents/categories` | `list_categories` |
| GET | `/documents/categories/tree` | `list_categories_tree` |
| GET | `/documents/categories/{cat_id}` | `get_category` |
| POST | `/documents/categories` | `create_category` |
| PATCH | `/documents/categories/{cat_id}` | `update_category` |
| DELETE | `/documents/categories/{cat_id}` | `delete_category` |

### ვერსიები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/documents/{doc_id}/versions` | `list_versions` |
| POST | `/documents/{doc_id}/versions` | `create_version` |
| GET | `/documents/{doc_id}/versions/{version_id}` | `get_version` |
| POST | `/documents/{doc_id}/versions/{version_id}/restore` | `restore_version` — ძველი ვერსიის აღდგენა |

### დამტკიცება და გამოქვეყნება

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| POST | `/documents/{doc_id}/submit-for-approval` | `submit_document_for_approval` |
| POST | `/documents/{doc_id}/approve` | `approve_document` |
| POST | `/documents/{doc_id}/publish` | `publish_document` |
| GET | `/documents/{doc_id}/approval-history` | `get_approval_history` |

### აუდიტი

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/documents/{doc_id}/audit-log` | `get_document_audit_log` |
| GET | `/documents/audit-log` | `list_document_audit_logs` |

## ბიზნეს ლოგიკა

- **ვერსიონირება:** ყოველი ცვლილება ქმნის ახალ ვერსიას, ძველის აღდგენა შესაძლებელია
- **დამტკიცების ნაკადი:** draft → submitted → approved → published
- **ვადები:** ვადაგასული დოკუმენტები ავტომატურად გამოდის სიაში
- **აუდიტი:** ყველა მოქმედება ფიქსირდება (ვინ, როდის, რა)

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
