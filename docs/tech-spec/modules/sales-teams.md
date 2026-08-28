# მოდული: SalesTeams (გაყიდვების გუნდები)

**კოდი:** `sales-teams`
**Route:** `/sales-teams`
**კატეგორია:** sales
**გვერდი:** `frontend/src/pages/SalesTeamsPage.tsx` (259 სტრიქონი)
**Backend:** `sales_teams.py`

---

## მიზანი

გაყიდვების გუნდების, მიზნების (targets) და საკომისიოს წესების მართვა — გაყიდვების სტიმულირება და კონტროლი.

## გვერდის სტრუქტურა

### 1. ტაბები

| ტაბი | ფუნქცია |
|------|----------|
| გუნდები | გუნდების მართვა |
| მიზნები | გაყიდვების მიზნები |
| საკომისიო | საკომისიოს წესები და დარიცხვები |

### 2. გუნდები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი გუნდი" | ღილაკი | გუნდის შექმნა |
| წევრების დამატება | select | `usersApi.list({page_size: 100})` |
| „შენახვა" | ღილაკი | გუნდის შენახვა |

### 3. საკომისიო

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „გადახდა" | ღილაკი | დარიცხული საკომისიოს გადახდა (`mark_commission_paid`) |

## API Endpoints

### გუნდები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/sales/teams/` | `list_teams` |
| POST | `/sales/teams/` | `create_team` |
| PATCH | `/sales/teams/{team_id}` | `update_team` |
| DELETE | `/sales/teams/{team_id}` | `delete_team` |
| POST | `/sales/teams/{team_id}/members` | `add_member` |
| DELETE | `/sales/teams/{team_id}/members/{user_id}` | `remove_member` |

### მიზნები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/sales/targets/` | `list_targets` |
| POST | `/sales/targets/` | `create_target` |
| PATCH | `/sales/targets/{target_id}` | `update_target` |
| DELETE | `/sales/targets/{target_id}` | `delete_target` |

### საკომისიო

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/sales/commission-rules/` | `list_commission_rules` |
| POST | `/sales/commission-rules/` | `create_commission_rule` |
| PATCH | `/sales/commission-rules/{rule_id}` | `update_commission_rule` |
| DELETE | `/sales/commission-rules/{rule_id}` | `delete_commission_rule` |
| GET | `/sales/commissions/` | `list_commissions` |
| POST | `/sales/commissions/{accrual_id}/mark-paid` | `mark_commission_paid` |

## ბიზნეს ლოგიკა

- **საკომისიოს დარიცხვა:** ხდება გაყიდვების მიხედვით, წესების მიხედვით (პროცენტი/ფიქსირებული)
- **მიზნები:** პერიოდული (თვიური/კვარტალური) გაყიდვების მიზნები გუნდისთვის/წევრისთვის

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
