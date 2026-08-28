# მოდული: HR (ადამიანური რესურსები)

**კოდი:** `hr`
**Route:** `/hr`
**კატეგორია:** other
**გვერდი:** `frontend/src/pages/HRPage.tsx` (995 სტრიქონი)
**Backend:** `hr.py`, `hr_enhanced.py`, `leaves.py`, `recruitment.py`

---

## მიზანი

ადამიანური რესურსების სრული მართვა: თანამშრომლები, დეპარტამენტები, დასწრება, შვებულებები, სახელფასო (payroll), სახელფასო ფურცლები (payslips), შეფასებები, ვაკანსიები, დოკუმენტები.

## გვერდის სტრუქტურა

### 1. ტაბები

| ტაბი | ფუნქცია |
|------|----------|
| თანამშრომლები | სია + CRUD |
| დეპარტამენტები | ორგანიზაციული სტრუქტურა |
| დასწრება | ყოფნა/არყოფნა |
| შვებულებები | მოთხოვნები + დამტკიცება |
| სახელფასო | ხელფასების გაანგარიშება |
| სახელფასო ფურცლები | payslips |
| შეფასებები | performance reviews |
| ვაკანსიები | რეკრუტინგი |
| დოკუმენტები | თანამშრომლის დოკუმენტები |

### 2. თანამშრომლები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „თანამშრომლის დამატება" | ღილაკი | შექმნის ფორმა |
| „რედაქტირება" | ღილაკი | თანამშრომლის ჩასწორება (`PATCH /hr/employees/{id}`) |
| თანამშრომლის რიგი | ცხრილი | სახელი, დეპარტამენტი, პოზიცია, ხელფასი, სტატუსი |

### 3. დასწრება

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „დასწრების დაფიქსირება" | ღილაკი | დღის დასწრების ჩაწერა (`POST /hr/attendance`) |
| „ახსნა" | ღილაკი | არყოფნის მიზეზი |

### 4. შვებულებები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „შვებულების მოთხოვნა" | ღილაკი | მოთხოვნის შექმნა (`POST /hr/leave-requests`) |
| „დამტკიცება" | ღილაკი | მოთხოვნის დამტკიცება (`approve_leave_request`) |
| „✕" | ღილაკი | მოთხოვნის გაუქმება (`cancel_leave_request`) |

### 5. სახელფასო

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „მუშავდება..." | ღილაკი | სახელფასოს გაანგარიშება (`POST /hr/payroll/calculate`) |
| „მუშავდება..." | ღილაკი | payslips-ის გენერაცია (`POST /hr/payslips/generate`) |

### 6. ვაკანსიები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი ვაკანსია" | ღილაკი | ვაკანსიის შექმნა (`POST /recruitment/`) |

### 7. შეფასებები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი შეფასება" | ღილაკი | შეფასების შექმნა (`POST /hr/performance-reviews`) |

### 8. დოკუმენტები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ახალი ჩანაწერი" | ღილაკი | დოკუმენტის დამატება (`POST /hr/documents`) |

## API Endpoints

### ძირითადი (`hr.py`)

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/hr/departments` | `list_departments` | დეპარტამენტები |
| POST | `/hr/departments` | `create_department` | |
| PATCH | `/hr/departments/{dept_id}` | `update_department` | |
| GET | `/hr/employees` | `list_employees` | თანამშრომლები |
| POST | `/hr/employees` | `create_employee` | |
| GET | `/hr/employees/{emp_id}` | `get_employee` | |
| PATCH | `/hr/employees/{emp_id}` | `update_employee` | |
| POST | `/hr/payroll/calculate` | `calculate_payroll` | სახელფასოს გაანგარიშება |
| GET | `/hr/payroll` | `list_payroll` | |
| PATCH | `/hr/payroll/{entry_id}` | `update_payroll_entry` | |
| GET | `/hr/timesheets` | `list_timesheets` | დროის ფურცლები |
| POST | `/hr/timesheets` | `create_timesheet` | |
| POST | `/hr/payslips/generate` | `generate_payslips` | payslips-ის გენერაცია |
| GET | `/hr/payslips` | `list_payslips` | |
| POST | `/hr/payslips/{payslip_id}/pay` | `pay_payslip` | გადახდა |
| GET | `/hr/leave-requests` | `list_leave_requests` | შვებულების მოთხოვნები |
| POST | `/hr/leave-requests` | `create_leave_request` | |
| POST | `/hr/leave-requests/{leave_id}/approve` | `approve_leave_request` | დამტკიცება |
| GET | `/hr/attendance` | `list_attendance` | დასწრება |
| POST | `/hr/attendance` | `create_attendance` | |
| GET | `/hr/reviews` | `list_reviews` | შეფასებები |
| POST | `/hr/reviews` | `create_review` | |

### გაფართოებული (`hr_enhanced.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/hr/analytics` | `hr_analytics` — HR ანალიტიკა |
| GET | `/hr/department-tree` | `department_tree` — ორგ. სტრუქტურა |
| GET | `/hr/departments/{dept_id}/children` | `department_children` |
| GET | `/hr/me` | `my_profile` — საკუთარი პროფილი |
| PATCH | `/hr/me` | `update_my_profile` |
| GET | `/hr/me/leave-balances` | `my_leave_balances` |
| GET | `/hr/me/leave-requests` | `my_leave_requests` |
| GET | `/hr/me/documents` | `my_documents` |
| GET | `/hr/me/performance-reviews` | `my_performance_reviews` |
| GET | `/hr/documents` | `list_employee_documents` |
| POST | `/hr/documents` | `create_employee_document` |
| GET | `/hr/documents/{doc_id}` | `get_employee_document` |
| PATCH | `/hr/documents/{doc_id}` | `update_employee_document` |
| POST | `/hr/documents/{doc_id}/verify` | `verify_employee_document` — დოკუმენტის დამოწმება |
| GET | `/hr/leave-types` | `list_leave_types` |
| POST | `/hr/leave-types` | `create_leave_type` |
| PATCH | `/hr/leave-types/{lt_id}` | `update_leave_type` |
| GET | `/hr/leave-balances` | `list_leave_balances` |
| POST | `/hr/leave-balances` | `create_leave_balance` |
| PATCH | `/hr/leave-balances/{lb_id}` | `update_leave_balance` |
| GET | `/hr/leave-requests/{lr_id}` | `get_leave_request` |
| POST | `/hr/leave-requests/{lr_id}/cancel` | `cancel_leave_request` |
| GET | `/hr/attendance-records` | `list_attendance_records` |
| POST | `/hr/attendance-records` | `create_attendance_record` |
| POST | `/hr/attendance-records/bulk` | `bulk_create_attendance` — მასობრივი დასწრება |
| PATCH | `/hr/attendance-records/{att_id}` | `update_attendance_record` |
| GET | `/hr/attendance` | `attendance_summary` |
| GET | `/hr/performance-reviews` | `list_performance_reviews` |
| POST | `/hr/performance-reviews` | `create_performance_review` |
| GET | `/hr/performance-reviews/{pr_id}` | `get_performance_review` |
| PATCH | `/hr/performance-reviews/{pr_id}` | `update_performance_review` |
| POST | `/hr/performance-reviews/{pr_id}/acknowledge` | `acknowledge_performance_review` |
| GET | `/hr/performance-goals` | `list_performance_goals` |
| PATCH | `/hr/performance-goals/{goal_id}` | `update_performance_goal` |
| GET | `/hr/payroll-summary` | `payroll_summary` |
| GET | `/hr/export/employees` | `export_employees` |
| GET | `/hr/export/payroll` | `export_payroll` |

### შვებულებები (`leaves.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/leaves/` | `list_leaves` |
| GET | `/leaves/{leave_id}` | `get_leave` |
| POST | `/leaves/` | `create_leave` |
| PATCH | `/leaves/{leave_id}` | `update_leave` |
| PATCH | `/leaves/{leave_id}/approve` | `approve_leave` |
| DELETE | `/leaves/{leave_id}` | `delete_leave` |

### ვაკანსიები (`recruitment.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/recruitment/` | `list_job_postings` |
| GET | `/recruitment/{job_posting_id}` | `get_job_posting` |
| POST | `/recruitment/` | `create_job_posting` |
| PATCH | `/recruitment/{job_posting_id}` | `update_job_posting` |
| DELETE | `/recruitment/{job_posting_id}` | `delete_job_posting` |

## Frontend API ზარები

- `GET /hr/employees` — თანამშრომლები
- `GET /hr/departments` — დეპარტამენტები
- `GET /hr/payroll` — სახელფასო
- `GET /hr/payslips` — payslips
- `GET /hr/leave-requests` — შვებულებები
- `GET /hr/attendance` — დასწრება
- `GET /hr/reviews` — შეფასებები
- `GET /recruitment/job-postings` — ვაკანსიები
- `GET /hr/timesheets` — დროის ფურცლები
- `PATCH /hr/employees/${editId}` — თანამშრომლის განახლება

## ბიზნეს ლოგიკა

- **სახელფასო გაანგარიშება:** ხელფასი + დანამატები − გამოქვითვები (წესები `payroll_rules.py`-ში)
- **Payslips:** გენერაცია პერიოდის მიხედვით, გადახდა ქმნის GL გატარებას
- **შვებულების ბალანსი:** ტიპების მიხედვით (ყოველწლიური, ავადმყოფობა, ...), მოთხოვნა ამცირებს ბალანსს დამტკიცებისას
- **დასწრება:** ყოველდღიური ჩაწერა, მასობრივი შეყვანა, შეჯამება
- **შეფასებები:** მიზნები + შეფასება, თანამშრომლის acknowledge
- **Self-service:** `/hr/me/*` — თანამშრომელი ხედავს საკუთარ მონაცემებს

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
