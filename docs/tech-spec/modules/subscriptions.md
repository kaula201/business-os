# მოდული: Subscriptions (გამოწერები)

**კოდი:** `subscriptions`
**Route:** `/subscriptions`
**კატეგორია:** sales
**დამოკიდებულია:** `invoices`
**გვერდი:** `frontend/src/pages/SubscriptionsPage.tsx` (143 სტრიქონი)
**Backend:** `subscriptions.py`

---

## მიზანი

განმეორებადი გამოწერების მართვა — პერიოდული გადახდები კლიენტებისგან (თვიური, წლიური, ერთჯერადი).

## გვერდის სტრუქტურა

### 1. სიის ხედი

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი გამოწერა" | ღილაკი | შექმნის ფორმა |
| გამოწერის რიგი | ცხრილი | კლიენტი, პერიოდი, თანხა, სტატუსი |

### 2. შექმნის ფორმა

| ველი | ტიპი | წყარო |
|------|------|-------|
| კლიენტი | select | `clientsApi.list({page_size: 100})` |
| პერიოდი | select | `monthly` / `yearly` / `one_time` |
| თანხა | input | |
| დაწყების თარიღი | input (date) | |

| ღილაკი | ფუნქცია |
|--------|----------|
| „შენახვა" | გამოწერის შენახვა |

## API Endpoints

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/subscriptions/` | `list_subscriptions` | სია |
| GET | `/subscriptions/{subscription_id}` | `get_subscription` | ერთი გამოწერა |
| POST | `/subscriptions/` | `create_subscription` | შექმნა |
| PATCH | `/subscriptions/{subscription_id}` | `update_subscription` | განახლება |
| POST | `/subscriptions/{subscription_id}/renew` | `renew_subscription` | განახლება (renew) |
| DELETE | `/subscriptions/{subscription_id}` | `delete_subscription` | წაშლა |

## ბიზნეს ლოგიკა

- **განახლება:** `renew` ქმნის ახალ პერიოდს და ინვოისს
- **პერიოდები:** monthly / yearly / one_time

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
