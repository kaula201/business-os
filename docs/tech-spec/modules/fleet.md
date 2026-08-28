# მოდული: Fleet (ავტოპარკი)

**კოდი:** `fleet`
**Route:** `/fleet`
**კატეგორია:** fleet
**გვერდი:** `frontend/src/pages/FleetPage.tsx` (995 სტრიქონი)
**Backend:** `fleet.py`, `fleet_enhanced.py`

---

## მიზანი

ავტოპარკის მართვა: ავტომობილები, საწვავის აღრიცხვა, მომსახურება, მძღოლების მინიჭება, ოდომეტრი, ანალიტიკა, რუკა (GeorgiaFleetMap).

## გვერდის სტრუქტურა

### 1. ტაბები

| ტაბი | ფუნქცია |
|------|----------|
| „ავტომობილი" | ავტომობილების სია + CRUD |
| „საწვავი" | საწვავის შევსების ჩანაწერები |
| „მომსახურება" | მომსახურების ჩანაწერები |
| „მძღოლი" | მძღოლების მინიჭება |

### 2. ავტომობილები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „იქმნება..." | ღილაკი | ავტომობილის შექმნა (`POST /fleet/vehicles`) |
| „ინახება..." | ღილაკი | ავტომობილის განახლება |
| „გაუქმება" | ღილაკი | ფორმის დახურვა |

### 3. საწვავი

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ინახება..." | ღილაკი | საწვავის ჩანაწერის შენახვა (`POST /fleet/vehicles/{id}/fuel-logs`) |

### 4. მომსახურება

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ინახება..." | ღილაკი | მომსახურების ჩანაწერი (`POST /fleet/vehicles/{id}/services`) |

### 5. მძღოლები

| ელემენტი | ტიპი | ფუნქცია |
|----------|------|----------|
| „ინახება..." | ღილაკი | მძღოლის მინიჭება (`POST /fleet/vehicles/{id}/drivers`) |

## API Endpoints

### ძირითადი (`fleet.py`)

| მეთოდი | Path | ფუნქცია | აღწერა |
|--------|------|---------|--------|
| GET | `/fleet/vehicles` | `list_vehicles` | ავტომობილები |
| GET | `/fleet/vehicles/{vehicle_id}` | `get_vehicle` | |
| POST | `/fleet/vehicles` | `create_vehicle` | |
| PUT | `/fleet/vehicles/{vehicle_id}` | `update_vehicle` | |
| DELETE | `/fleet/vehicles/{vehicle_id}` | `delete_vehicle` | |
| GET | `/fleet/vehicles/{vehicle_id}/fuel-logs` | `list_fuel_logs` | საწვავი |
| POST | `/fleet/vehicles/{vehicle_id}/fuel-logs` | `create_fuel_log` | |
| DELETE | `/fleet/fuel-logs/{log_id}` | `delete_fuel_log` | |
| GET | `/fleet/vehicles/{vehicle_id}/services` | `list_service_records` | მომსახურება |
| POST | `/fleet/vehicles/{vehicle_id}/services` | `create_service_record` | |
| DELETE | `/fleet/services/{record_id}` | `delete_service_record` | |
| GET | `/fleet/vehicles/{vehicle_id}/drivers` | `list_driver_assignments` | მძღოლები |
| POST | `/fleet/vehicles/{vehicle_id}/drivers` | `create_driver_assignment` | |
| PUT | `/fleet/drivers/{assignment_id}` | `update_driver_assignment` | |
| DELETE | `/fleet/drivers/{assignment_id}` | `delete_driver_assignment` | |
| GET | `/fleet/vehicles/{vehicle_id}/odometer` | `list_odometer_readings` | ოდომეტრი |
| POST | `/fleet/vehicles/{vehicle_id}/odometer` | `create_odometer_reading` | |
| DELETE | `/fleet/odometer/{reading_id}` | `delete_odometer_reading` | |

### გაფართოებული (`fleet_enhanced.py`)

| მეთოდი | Path | ფუნქცია |
|--------|------|---------|
| GET | `/fleet/fuel-report` | `fuel_consumption_report` — საწვავის მოხმარება |
| GET | `/fleet/service-alerts` | `service_alerts` — მომსახურების გაფრთხილებები |
| GET | `/fleet/analytics` | `fleet_analytics` — ანალიტიკა |
| GET | `/fleet/export/vehicles` | `export_vehicles` — ექსპორტი |

## ბიზნეს ლოგიკა

- **საწვავის მოხმარება:** ლიტრი/100კმ ითვლება ოდომეტრის და საწვავის ჩანაწერებიდან
- **მომსახურების გაფრთხილებები:** ბოლო მომსახურების გარბენის/თარიღის მიხედვით
- **მძღოლის ისტორია:** მინიჭებები დროის მიხედვით
- **რუკა:** GeorgiaFleetMap კომპონენტი აჩვენებს ავტომობილების განლაგებას

## ცვლილებების ჟურნალი

| თარიღი | ცვლილება |
|--------|----------|
| 2026-08-28 | პირველი აღწერა (ავტო-სკანერის მონაცემებით) |
