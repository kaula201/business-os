# მოდული: Helpdesk (მხარდაჭერა)

**კოდი:** `helpdesk`
**Route:** `/helpdesk`
**კატეგორია:** operations
**დამოკიდებულია:** `tasks`
**გვერდი:** `frontend/src/pages/HelpdeskPage.tsx` (825 სტრიქონი)
**Backend:** `helpdesk.py`

---

## მიზანი

მხარდაჭერის ტიკეტების სრული მართვა: ტიკეტები, გუნდები, pipelines, SLA, ესკალაციები, ცოდნის ბაზა, field service, კმაყოფილების შეფასება.

## გვერდის სტრუქტურა

### 1. ტიკეტების სია

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| ტიკეტის რიგი | ცხრილი | ნომერი, სათაური, პრიორიტეტი, სტატუსი, პასუხისმგებელი |
| „+" | ღილაკი | ახალი ტიკეტი |
| „✓" | ღილაკი | ტიკეტის დახურვა |

### 2. ტიკეტის დეტალები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „გაგზავნა" | ღილაკი | შეტყობინების გაგზავნა (`add_ticket_message`) |
| „შენახვა" | ღილაკი | ტიკეტის განახლება |
| კლიენტი | select | `clientsApi.list({page_size: 100})` |
| პასუხისმგებელი | select | `usersApi.list({page_size: 100})` |

### 3. დამატებითი სექციები

- გუნდები, pipelines, queues, SLA, ესკალაციები, canned replies, ცოდნის ბაზა, field service

## API Endpoints

### ტიკეტები

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/helpdesk/` | `list_tickets` |
| GET | `/helpdesk/{ticket_id:uuid}` | `get_ticket` |
| POST | `/helpdesk/` | `create_ticket` |
| PUT | `/helpdesk/{ticket_id:uuid}` | `update_ticket` |
| DELETE | `/helpdesk/{ticket_id:uuid}` | `delete_ticket` |
| GET | `/helpdesk/{ticket_id:uuid}/messages` | `list_ticket_messages` |
| POST | `/helpdesk/{ticket_id:uuid}/messages` | `add_ticket_message` |
| GET | `/helpdesk/{ticket_id:uuid}/followers` | `list_followers` |
| POST | `/helpdesk/{ticket_id:uuid}/followers` | `add_follower` |
| POST | `/helpdesk/{ticket_id:uuid}/attachments` | `upload_attachment` |
| GET | `/helpdesk/{ticket_id:uuid}/attachments` | `list_attachments` |
| POST | `/helpdesk/{ticket_id:uuid}/time-spent` | `add_time_spent` |
| POST | `/helpdesk/{ticket_id:uuid}/satisfaction` | `rate_satisfaction` |
| GET | `/helpdesk/{ticket_id:uuid}/kb-suggestions` | `kb_suggestions` |

### ორგანიზაცია

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/helpdesk/teams` | `list_teams` |
| POST | `/helpdesk/teams` | `create_team` |
| POST | `/helpdesk/teams/{id}/members` | `add_team_member` |
| DELETE | `/helpdesk/teams/{id}` | `delete_team` |
| GET | `/helpdesk/pipelines` | `list_pipelines` |
| POST | `/helpdesk/pipelines` | `create_pipeline` |
| DELETE | `/helpdesk/pipelines/{id}` | `delete_pipeline` |
| GET | `/helpdesk/queues` | `list_queues` |
| POST | `/helpdesk/queues` | `create_queue` |

### SLA და ესკალაცია

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/helpdesk/slas` | `list_slas` |
| POST | `/helpdesk/slas` | `create_sla` |
| GET | `/helpdesk/escalations` | `list_escalations` |
| POST | `/helpdesk/escalations` | `create_escalation` |

### ცოდნის ბაზა

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/helpdesk/canned-replies` | `list_canned_replies` |
| POST | `/helpdesk/canned-replies` | `create_canned_reply` |
| GET | `/helpdesk/knowledge` | `list_knowledge` |
| POST | `/helpdesk/knowledge` | `create_knowledge` |

### Field Service

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/helpdesk/field-service` | `list_field_service` |
| GET | `/helpdesk/field-service/my-jobs` | `my_field_service_jobs` |
| POST | `/helpdesk/field-service` | `create_field_service` |
| POST | `/helpdesk/field-service/{id}/start` | `start_field_service` |
| POST | `/helpdesk/field-service/{id}/complete` | `complete_field_service` |

### ელ.ფოსტის მიღება

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/helpdesk/email-intake` | `list_email_intake` |
| POST | `/helpdesk/email-intake` | `create_email_intake` |

## ბიზნეს ლოგიკა

- **SLA:** ტიკეტის პასუხის/გადაჭრის ვადები პრიორიტეტის მიხედვით
- **ესკალაცია:** SLA-ს დარღვევისას ტიკეტი ავტომატურად ესკალირდება
- **Field service:** გამოძახებები ადგილზე — start/complete ციკლი
- **KB სუგესციები:** ტიკეტის ტექსტზე დაფუძნებული ცოდნის ბაზის წინადადებები

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
