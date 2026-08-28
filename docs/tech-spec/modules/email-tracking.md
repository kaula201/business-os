# მოდული: EmailTracking (ელ.ფოსტა და ხელმოწერები)

**კოდი:** `email-tracking`
**Route:** `/email-tracking`
**კატეგორია:** sales
**გვერდი:** `frontend/src/pages/EmailTrackingPage.tsx` (140 სტრიქონი)
**Backend:** `email_tracking.py`, `email_marketing.py`

---

## მიზანი

ელ.ფოსტის მოვლენების (გახსნა, დაწკაპუნება) თრექინგი, ელექტრონული ხელმოწერის (e-signature) მოთხოვნები და ელ.ფოსტის კამპანიები.

## გვერდის სტრუქტურა

### 1. ტაბები

| ტაბი | ფუნქცია |
|------|----------|
| „ელ.ფოსტის მოვლენები" | გახსნის/დაწკაპუნების ისტორია |
| „ხელმოწერის მოთხოვნები" | e-signature მოთხოვნები |

### 2. ხელმოწერის მოთხოვნა

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი ხელმოწერის მოთხოვნა" | ღილაკი | მოთხოვნის შექმნა |
| „გაგზავნა" | ღილაკი | მოთხოვნის გაგზავნა (`POST /signature-requests/{id}/resend`) |

## API Endpoints

### ელ.ფოსტის მოვლენები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| POST | `/email-events/` | `record_email_event` — მოვლენის ჩაწერა (webhook) |
| GET | `/email-events/` | `list_email_events` — მოვლენების სია |
| GET | `/email-campaigns/{id}/stats` | `campaign_stats` — კამპანიის სტატისტიკა |

### ხელმოწერები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/signature-requests/` | `list_signature_requests` |
| POST | `/signature-requests/` | `create_signature_request` |
| POST | `/signature-requests/{id}/resend` | `resend_signature_request` — ხელახლა გაგზავნა |
| POST | `/signature-requests/sign` | `sign_request` — ხელმოწერა |

### კამპანიები (`email_marketing.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/email-campaigns/` | `list_email_campaigns` |
| GET | `/email-campaigns/{id}` | `get_email_campaign` |
| POST | `/email-campaigns/` | `create_email_campaign` |
| PATCH | `/email-campaigns/{id}` | `update_email_campaign` |
| POST | `/email-campaigns/{id}/send` | `send_campaign` — გაგზავნა |
| DELETE | `/email-campaigns/{id}` | `delete_email_campaign` |

## ბიზნეს ლოგიკა

- **SMTP:** თუ `SMTP_HOST` დაყენებულია — რეალური გაგზავნა; თორემ sandbox (`email_messages` ცხრილი)
- **e-signature:** მოთხოვნა უკავშირდება დოკუმენტს, აქვს ვადა და ხელახლა გაგზავნის შესაძლებლობა

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
