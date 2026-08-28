# მოდული: AccountingPeriods (სააღრიცხვო პერიოდები)

**კოდი:** `accounting-periods`
**Route:** `/accounting-periods`
**კატეგორია:** accounting
**გვერდი:** `frontend/src/pages/AccountingPeriodsPage.tsx` (212 სტრიქონი)
**Backend:** `accounting_periods.py`, `accounting_periods_enhanced.py`

---

## მიზანი

სააღრიცხვო პერიოდების მართვა: გახსნა, დახურვა, ხელახლა გახსნა, დახურვის ისტორია და დახურვის წინასწარი შემოწმება (checklist).

## გვერდის სტრუქტურა

### 1. პერიოდების სია

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| წლის ფილტრი | select | `GET /accounting-periods?year=${year}` |
| „გახსნა" | ღილაკი | პერიოდის გახსნა |
| „დახურვა" | ღილაკი | პერიოდის დახურვა |
| „ისტორია" | ღილაკი | დახურვის ისტორია |
| „პერიოდის დახურვა" | ღილაკი | დახურვის დადასტურება |
| „მუშავდება..." | ღილაკი | GL ავტომატიზაციის გაშვება (`POST /gl/automation/run`) |

## API Endpoints

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| POST | `/accounting-periods/{year}/{month}/close` | `close_period` | დახურვა |
| POST | `/accounting-periods/{year}/{month}/reopen` | `reopen_period` | ხელახლა გახსნა |
| GET | `/accounting-periods/{period_id}/history` | `period_history` | ისტორია |
| GET | `/accounting-periods/{year}/{month}/close-checklist` | `period_close_checklist` | დახურვის შემოწმება |

## ბიზნეს ლოგიკა

- **დახურვა:** დახურულ პერიოდში ახალი ჩანაწერები აკრძალულია
- **Checklist:** დახურვამდე ამოწმებს: ყველა ინვოისი დადასტურებულია, ბანკი შეჯერებულია, ამორტიზაცია გატარებულია
- **Reopen:** შეცდომის შემთხვევაში პერიოდის ხელახლა გახსნა (ისტორიით)

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
