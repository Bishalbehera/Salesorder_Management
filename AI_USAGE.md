# AI Usage Disclosure (AI_USAGE.md)

As required by **Part 14** of the technical assignment for Savyant Systems, this document details how AI assistance was utilized throughout development.

---

## 1. Tools Used
- **Google DeepMind Antigravity AI Assistant** (powered by Gemini models)
- **Built-in Python 3.14 / Django 6.0 tooling and static code analysis**

---

## 2. Usage Tasks
AI was utilized for:
1. **Database Schema & Architecture Modeling:** Designing normalized relational entities (`User`, `Customer`, `Product`, `SalesOrder`, `SalesOrderItem`, `StockMovement`) with explicit constraints, foreign key cascades, and database indexes.
2. **Transactional Concurrency Implementation:** Formulating `select_for_update()` row locking patterns inside `transaction.atomic()` to guarantee that concurrent order confirmations never over-allocate or produce negative stock.
3. **Automated Test Scenarios Generation:** Scaffolding unit and integration tests covering all 9 mandatory business edge cases, including permission enforcement and CSV rollback.
4. **Interactive JavaScript State Logic:** Writing modular client-side dynamic row rendering, live financial recalculation with 2-decimal precision, and duplicate submission prevention.

---

## 3. Example Prompts
Below are three representative prompts used during development:

### Prompt 1: Transactional Concurrency & Stock Locks
> *"Design a concurrency-safe Django service for confirming sales orders where multiple users might confirm orders for the same limited inventory simultaneously. Ensure atomic rollback if any item has insufficient stock, prevent race conditions using row-level locking, and record stock movement audit logs in the same database transaction."*

### Prompt 2: All-or-Nothing CSV Import with Row Error Reporting
> *"Implement an Admin-only product CSV import service in Python/Django that validates columns, formats, uniqueness of codes against existing DB records, and negative values. If even a single row is invalid, roll back the entire transaction (import nothing) and return an array of row numbers with human-readable error reasons."*

### Prompt 3: Part 11 Bug Analysis & Robust Implementation
> *"Analyze the calculate_total() function from the assignment. Detail why total = amount causes an incorrect result of 150 instead of 350, and rewrite a production-grade version using Decimal arithmetic, handling empty lists, missing keys, and rejecting negative or invalid numbers."*

---

## 4. Review Approach
All AI-generated code was verified through the following verification workflow:
1. **Automated Test Suite Verification:** Executed `python manage.py test` (19 scenarios) and `python -m unittest test_debugging.py` (8 scenarios) to programmatically ensure 100% compliance with assignment specifications.
2. **Boundary Testing:** Verified edge cases including 0 quantity, negative quantity, discount values above 20%, empty CSV files, duplicate codes, and cross-user URL manipulation.
3. **Manual Verification:** Logged into the application as both `admin@savyant.com` and `sales1@savyant.com`, validating UI responsiveness, permissions, live calculation, and CSRF protection.
4. **SQL Verification:** Validated all 5 standalone MySQL queries against relational schemas to ensure no double-counting of orders across line items.

---

## 5. Corrections & Issues Identified
- **Issue with Order Cancellation Stock Restores:**
  - *Identified:* An initial draft allowed repeated cancellation requests to continuously increment stock back into the product inventory if called multiple times.
  - *Correction:* Added strict state validation (`if order.status == SalesOrder.STATUS_CANCELLED: return order`) and checked previous state so that stock restoration only occurs once when transitioning from `Confirmed` to `Cancelled`.
- **Double Counting in Aggregated Customer Reports:**
  - *Identified:* Joining `Customer -> SalesOrder -> SalesOrderItem` caused customer grand totals to be multiplied by the number of item lines in each order.
  - *Correction:* Refactored the ORM query and standalone SQL queries to use `COUNT(DISTINCT so.id)` and `SUM(so.grand_total)` grouped on order ID before customer rollup, ensuring order grand totals are counted exactly once.
