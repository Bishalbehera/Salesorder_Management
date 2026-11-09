# Savyant Systems — Sales Order & Inventory Management

A full-stack Django web application fulfilling the **Fresher/Trainee Technical Assignment** requirements.

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Backend Framework | **Django 6.0** (Python 3.14) |
| REST API | **Django REST Framework 3.16** |
| Database | **SQLite** (default) / **MySQL 8.0** (via PyMySQL) |
| Frontend | **Django Templates** + vanilla **CSS** + **Vanilla JS** |
| Tests | **Django TestCase** + **DRF APIClient** |

> No Flask, no React, no Celery, no Redis — only the technologies specified in the PDF.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy env template and configure
copy .env.example .env

# 3. Apply migrations
python manage.py migrate

# 4. Seed sample data (users, products, customers, orders)
python seed_data.py

# 5. Run the server
python manage.py runserver
```

Open **http://127.0.0.1:8000** in your browser.

---

## Sample Login Credentials

| Role | Email | Password |
|------|-------|----------|
| **Admin** | admin@savyant.com | Admin@123 |
| **Sales User 1** | sales1@savyant.com | Sales@123 |
| **Sales User 2** | sales2@savyant.com | Sales@123 |

---

## MySQL Configuration (optional)

Edit `.env` and set:
```env
DB_ENGINE=mysql
DB_NAME=savyant_sales_db
DB_USER=root
DB_PASSWORD=yourpassword
DB_HOST=127.0.0.1
DB_PORT=3306
```
Then run `python manage.py migrate`.

---

## Project Structure

```
project_demo/
├── sales_inventory_project/   # Django project config (settings, urls, wsgi)
├── sales_core/                # Core application
│   ├── models.py              # User, Customer, Product, SalesOrder, SalesOrderItem, StockMovement
│   ├── services.py            # OrderService, StockService, CSVImportService (all business logic)
│   ├── views.py               # Web (HTML) views — auth, CRUD, reports, CSV import
│   ├── api_views.py           # REST API endpoints (Part 8)
│   ├── serializers.py         # DRF serializers
│   ├── urls.py                # URL routing (web + API)
│   └── tests.py               # 11 automated test cases (Part 12)
├── templates/                 # Django HTML templates
│   ├── auth/                  # Login
│   ├── customers/             # Customer list, form, delete
│   ├── products/              # Product list, form, delete, stock adjust
│   ├── orders/                # Order list, create, detail
│   ├── reports/               # 4 report pages
│   └── csv_import/            # CSV upload & error display
├── static/
│   ├── css/styles.css         # Custom CSS (no external CSS libraries)
│   └── js/
│       ├── main.js            # Duplicate submit prevention, confirm dialogs
│       └── order_form.js      # Dynamic rows, live totals, API price fetch
├── schema.sql                 # MySQL DDL with constraints and sample INSERTs
├── standalone_queries.sql     # 5 standalone SQL queries (Part 9)
├── debugging_exercise.py      # Buggy + corrected calculate_total() (Part 11)
├── test_debugging.py          # 8 unit tests for calculate_total()
├── seed_data.py               # Database seeder
├── sample_valid.csv           # Valid CSV for import demo
├── sample_invalid.csv         # Invalid CSV to demonstrate all-or-nothing rollback
├── api_collection.json        # Postman API collection (Part 8)
├── DEBUGGING.md               # Written analysis of the debugging exercise
└── AI_USAGE.md                # AI usage disclosure (Part 14)
```

---

## Feature Coverage by Assignment Part

| Part | Requirement | Implementation |
|------|-------------|----------------|
| Part 1 | Tech Stack | Django 6, DRF, PyMySQL, Python 3.14 |
| Part 2 | Role-based Auth | Custom User model with `admin`/`sales` roles, enforced in every view + API |
| Part 3 | Database Design | 6 normalized models with FK constraints, `PROTECT`/`CASCADE`, DB indexes |
| Part 4 | Customer & Product CRUD | Full CRUD with active/inactive toggle, safe-delete guard |
| Part 5 | Sales Order Logic | Draft → Confirmed → Cancelled lifecycle with backend calculation |
| Part 6 | Stock Management | Auto-deduction on confirm, restore on cancel, manual adjustment with reason |
| Part 7 | Interactive Order Form | Dynamic JS rows, live calculation, API price fetch, duplicate-submit prevention |
| Part 8 | REST API | 6 JSON endpoints: list products, get product, create/get/confirm/cancel order |
| Part 9 | SQL Queries | 5 standalone queries: top customers, top products, never-ordered, monthly sales, low stock |
| Part 10 | CSV Import | All-or-nothing with per-row error reporting and opening stock movement |
| Part 11 | Debugging Exercise | Bug identified, corrected, edge-cases handled, `DEBUGGING.md` written |
| Part 12 | Automated Tests | 19 Django + 8 unittest tests covering all specified scenarios |
| Part 13 | Git Branching | `main` branch + `feature/order-concurrency-and-csv-import` branch merged |
| Part 14 | AI Disclosure | `AI_USAGE.md` with prompts, tools, and corrections |

---

## Running Tests

```bash
# Django integration + API tests (19 tests)
python manage.py test

# Standalone debugging exercise unit tests (8 tests)
python -m unittest test_debugging.py
```

---

## REST API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/products/` | List active products (search + pagination) |
| GET | `/api/products/<id>/` | Get product details (price + stock) |
| POST | `/api/orders/` | Create draft order |
| GET | `/api/orders/<id>/` | Get order detail (role-enforced) |
| POST | `/api/orders/<id>/confirm/` | Confirm order and deduct stock |
| POST | `/api/orders/<id>/cancel/` | Cancel order and restore stock |

> Import `api_collection.json` into Postman. Set `base_url` variable to `http://127.0.0.1:8000`.

---

## Key Business Rules Enforced

- **Quantities** must be positive whole integers (> 0)
- **Discount** must be between 0% and 20% (inclusive)
- **Prices** and **stock quantities** cannot be negative
- **Calculations** use Python `Decimal` with `ROUND_HALF_UP` to prevent floating-point errors
- **Order confirmation** uses `select_for_update()` row locking — concurrent confirmations are race-condition safe
- If ANY product has insufficient stock, the ENTIRE confirmation is rejected atomically
- **Stock is never negative** — adjustment and confirm operations both enforce this
- **Cancelled orders** are permanently read-only
- **Sales Users** can only view/confirm/cancel their own orders
- **CSV Import** is all-or-nothing: a single invalid row blocks the entire import
