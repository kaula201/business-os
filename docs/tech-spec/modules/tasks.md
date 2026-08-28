# მოდული: Tasks (დავალებები)

**კოდი:** `tasks`
**Route:** `/tasks`
**კატეგორია:** operations
**გვერდი:** `frontend/src/pages/TasksPage.tsx` (466 სტრიქონი)
**Backend:** `tasks.py`, `tasks_enhanced.py`

---

## მიზანი

დავალებების მართვა: სია, Kanban დოსკა, კალენდარი, Gantt, კომენტარები, დამოკიდებულებები, შეხსენებები.

## გვერდის სტრუქტურა

### 1. ხედები

| ღილაკი | ფუნქცია |
|--------|----------|
| „სია" | ცხრილის ხედი |
| „დოსკა" | Kanban ხედი (`GET /tasks/kanban`) |
| „კალენდარი" | კალენდრის ხედი (`GET /tasks/calendar`) |
| „Gantt" | Gantt დიაგრამა |

### 2. სია

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| ძებნა | input | `tasksApi.list({search})` |
| „ახალი დავალება" | ღილაკი | შექმნის ფორმა |
| „ყველა" | ღილაკი | ფილტრის გასუფთავება |
| „პრიორიტეტი" | ფილტრი | პრიორიტეტის მიხედვით |
| „განახლება" | ღილაკი | დავალების შენახვა |
| „გაგზავნა" | ღილაკი | კომენტარის გაგზავნა |

### 3. ფორმა

| ველი | ტიპი | წყარო |
|------|------|-------|
| პასუხისმგებელი | select | `usersApi.list({page_size: 100})` |
| კლიენტი | select | `clientsApi.list({page_size: 100})` |
| პრიორიტეტი | select | |
| ვადა | input (date) | |

## API Endpoints

### ძირითადი (`tasks.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/tasks/` | `list_tasks` |
| GET | `/tasks/{task_id}` | `get_task` |
| POST | `/tasks/` | `create_task` |
| PATCH | `/tasks/{task_id}` | `update_task` |
| GET | `/tasks/{task_id}/comments` | `list_comments` |
| POST | `/tasks/{task_id}/comments` | `add_comment` |
| GET | `/tasks/{task_id}/attachments` | `list_attachments` |
| POST | `/tasks/{task_id}/attachments` | `upload_attachment` |
| DELETE | `/tasks/{task_id}/attachments/{id}` | `delete_attachment` |
| GET | `/tasks/{task_id}/history` | `list_history` |
| GET | `/tasks/{task_id}/activity` | `get_activity_feed` |
| GET | `/tasks/{task_id}/reminders` | `list_reminders` |
| POST | `/tasks/{task_id}/reminders` | `create_reminder` |
| PATCH | `/tasks/{task_id}/reminders/{id}` | `update_reminder` |
| DELETE | `/tasks/{task_id}/reminders/{id}` | `delete_reminder` |
| GET | `/tasks/{task_id}/dependencies` | `list_dependencies` |
| GET | `/tasks/{task_id}/dependents` | `list_dependents` |
| POST | `/tasks/{task_id}/dependencies` | `create_dependency` |
| DELETE | `/tasks/{task_id}/dependencies/{id}` | `delete_dependency` |

### გაფართოებული (`tasks_enhanced.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/tasks/kanban` | `task_kanban` |
| GET | `/tasks/calendar` | `task_calendar` |
| GET | `/tasks/analytics` | `task_analytics` |
| POST | `/tasks/bulk/status` | `bulk_update_task_status` |
| GET | `/tasks/export` | `export_tasks` |

## ბიზნეს ლოგიკა

- **დამოკიდებულებები:** დავალება შეიძლება იყოს სხვაზე დამოკიდებული (blocked by)
- **შეხსენებები:** პერიოდული შეტყობინებები ვადის მოახლოებისას
- **ისტორია:** ყველა ცვლილება ფიქსირდება

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
