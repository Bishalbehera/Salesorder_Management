# Part 11: Debugging Exercise Report

## 1. Cause of the Incorrect Result
In the original snippet:
```python
def calculate_total(items):
    total = 0
    for item in items:
        amount = item["qty"] * item["rate"]
        total = amount  # <-- CRITICAL BUG: Reassignment instead of accumulation
    return total
```
The variable `total` was re-assigned to `amount` on every pass of the `for` loop, rather than accumulating with `total += amount` or using an accumulator. 

For the input:
```python
items = [
    {"qty": 2, "rate": 100},  # amount = 200 -> total = 200
    {"qty": 3, "rate": 50}    # amount = 150 -> total = 150 (overwrites 200!)
]
```
The loop leaves `total` equal only to the **last** element's line amount ($150) instead of the sum ($200 + $150 = $350).

---

## 2. Behaviour for an Empty List
- **Requirement:** When passed an empty list `[]` (or `None`), the function should return `0.00` without throwing `IndexError` or unexpected exceptions.
- **Implementation:**
  ```python
  if items is None or len(items) == 0:
      return Decimal('0.00')
  ```
  Returns `Decimal('0.00')`.

---

## 3. Behaviour When Quantity or Rate is Missing
- **Requirement:** Gracefully handle missing keys or `None` values rather than throwing raw unhandled `KeyError` or `TypeError`.
- **Implementation:**
  The corrected function checks if `'qty'` and `'rate'` exist in each dictionary item and are not `None`.
  If missing:
  ```python
  if "qty" not in item:
      raise ValueError(f"Item at index {idx - 1} is missing mandatory key 'qty'.")
  if "rate" not in item:
      raise ValueError(f"Item at index {idx - 1} is missing mandatory key 'rate'.")
  ```
  This provides explicit error messages detailing the exact row and missing field.

---

## 4. Validation of Invalid Quantities and Rates
Financial and inventory calculations must strictly guard against corrupt data:
1. **Whole Number Quantities:**
   - Quantities are parsed as integers: `qty = int(qty_raw)`.
   - Rejects negative quantities (`qty < 0`).
2. **Monetary Decimal Precision:**
   - Instead of floating-point arithmetic (which can produce artifacts like `0.1 + 0.2 = 0.30000000000000004`), rates and amounts are parsed using `Decimal` and quantized to 2 decimal places using `ROUND_HALF_UP`.
   - Rejects negative rates (`rate < Decimal('0.00')`).
   - Rejects non-numeric strings or invalid objects with `ValueError`.

---

## 5. Corrected Function Reference
The corrected function is implemented in [debugging_exercise.py](file:///b:/bishal/project_demo/debugging_exercise.py) and thoroughly tested in [test_debugging.py](file:///b:/bishal/project_demo/test_debugging.py).
