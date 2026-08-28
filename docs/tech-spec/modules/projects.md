# მოდული: Projects (პროექტები)

**კოდი:** `projects`
**Route:** `/projects`
**კატეგორია:** operations
**გვერდი:** `frontend/src/pages/ProjectsPage.tsx` (331 სტრიქონი)
**Backend:** `projects.py`

---

## მიზანი

პროექტების მართვა: პროექტები, შაბლონები, milestones, წევრები (ალოკაცია/ტარიფი), timesheets (საათები → ხარჯი), მომგებიანობა, რესურსების დატვირთულობა.

## გვერდის სტრუქტურა

### 1. პროექტების სია

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი პროექტი" | ღილაკი | შექმნის ფორმა |
| „შაბლონები" | ღილაკი | შაბლონების მართვა |
| „დეტალები" | ღილაკი | პროექტის დეტალები |
| პროექტის რიგი | ცხრილი | სახელი, კლიენტი, სტატუსი, ბიუჯეტი, პროგრესი |

### 2. შექმნის ფორმა

| ველი | ტიპი | შენიშვნა |
|------|------|----------|
| სახელი | input | |
| კლიენტი | select | |
| ბიუჯეტი | input | |
| დაწყება/დასრულება | input (date) | |
| შაბლონიდან | select | `POST /projects/templates/{id}/instantiate` |

| ღილაკი | ფუნქცია |
|--------|----------|
| „პროექტის შექმნა" | შექმნა (`POST /projects/`) |
| „ინახება..." | განახლება |

### 3. Milestones

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი milestone" | ღილაკი | შექმნა (`POST /projects/{id}/milestones`) |
| „შენახვა" | ღილაკი | milestone-ის შენახვა |

## API Endpoints

### პროექტები

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/projects/` | `list_projects` | სია |
| POST | `/projects/` | `create_project` | შექმნა |
| GET | `/projects/{project_id}` | `get_project` | |
| PATCH | `/projects/{project_id}` | `update_project` | |
| DELETE | `/projects/{project_id}` | `delete_project` | |
| GET | `/projects/{project_id}/progress` | `get_project_progress` | პროგრესი |
| GET | `/projects/{project_id}/profitability` | `get_project_profitability` | მომგებიანობა |

### შაბლონები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/projects/templates` | `list_templates` |
| POST | `/projects/templates` | `create_template` |
| POST | `/projects/templates/{template_id}/instantiate` | `instantiate_template` — შაბლონიდან პროექტი |
| DELETE | `/projects/templates/{template_id}` | `delete_template` |

### Milestones

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/projects/{project_id}/milestones` | `list_milestones` |
| POST | `/projects/{project_id}/milestones` | `create_milestone` |
| PATCH | `/projects/{project_id}/milestones/{milestone_id}` | `update_milestone` |
| DELETE | `/projects/{project_id}/milestones/{milestone_id}` | `delete_milestone` |

### წევრები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/projects/{project_id}/members` | `list_project_members` |
| POST | `/projects/{project_id}/members` | `add_project_member` — ალოკაცია + ტარიფი |
| PATCH | `/projects/members/{member_id}` | `update_project_member` |
| DELETE | `/projects/members/{member_id}` | `remove_project_member` |

### Timesheets

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/projects/{project_id}/timesheets` | `list_project_timesheets` |
| POST | `/projects/{project_id}/timesheets` | `add_timesheet_entry` — საათები |
| DELETE | `/projects/timesheets/{entry_id}` | `delete_timesheet_entry` |

### რესურსები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/projects/resources/utilization` | `resource_utilization` — დატვირთულობის dashboard |

## ბიზნეს ლოგიკა

- **წევრები:** თანამშრომელი + ალოკაციის პროცენტი + საათობრივი ტარიფი
- **Timesheets:** საათები → ხარჯის rollup (საათები × ტარიფი)
- **მომგებიანობა:** შემოსავალი (ბიუჯეტი/ინვოისები) − ხარჯები (timesheets)
- **შაბლონები:** სტანდარტული პროექტის სტრუქტურა (milestones + წევრები) ერთი დაჭერით
- **რესურსების დატვირთულობა:** ვინ რამდენად არის დაკავებული პროექტებზე

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
