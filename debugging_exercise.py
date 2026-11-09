"""
Part 11: Debugging Exercise - Savyant Systems Technical Assignment
Topic: Item Total Calculation Bug Identification, Correction, and Hardening
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import List, Dict, Any, Union


def buggy_calculate_total(items):
    """
    ORIGINAL BUGGY FUNCTION (from prompt):
    Bug: Inside the loop, `total = amount` overwrites the accumulated sum on every iteration.
    Instead of adding each line item amount to the running total, it simply stores the last item's amount.
    For items = [{'qty': 2, 'rate': 100}, {'qty': 3, 'rate': 50}],
    Iteration 1: amount = 2 * 100 = 200, total = 200
    Iteration 2: amount = 3 * 50 = 150, total = 150 (overwrites 200!)
    Result: 150 instead of 350.
    """
    total = 0
    for item in items:
        amount = item["qty"] * item["rate"]
        total = amount
    return total


def calculate_total(items: List[Dict[str, Any]]) -> Decimal:
    """
    CORRECTED & HARDENED FUNCTION:
    
    1. Accumulation Fix:
       Uses `total += amount` instead of reassignment `total = amount`.
       
    2. Empty List Handling:
       If `items` is None, empty list `[]`, or falsy, safely returns `Decimal('0.00')`.
       
    3. Missing Keys Handling:
       Raises ValueError with a clear descriptive message if 'qty' or 'rate' is missing.
       
    4. Data Validation:
       - Validates that quantity is a non-negative integer (whole number >= 0).
       - Validates that rate is a non-negative number.
       - Uses Python's `Decimal` with `ROUND_HALF_UP` to prevent floating-point inaccuracy.
       
    Args:
        items: List of dictionaries each containing 'qty' and 'rate'.
        
    Returns:
        Decimal: Total amount rounded to 2 decimal places.
        
    Raises:
        TypeError: If items is not an iterable of dicts.
        ValueError: If 'qty' or 'rate' is missing, non-numeric, or negative.
    """
    if items is None:
        return Decimal('0.00')

    if not isinstance(items, list):
        raise TypeError(f"Expected items to be a list, received {type(items).__name__}")

    if len(items) == 0:
        return Decimal('0.00')

    total = Decimal('0.00')

    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise TypeError(f"Item at index {idx - 1} must be a dictionary.")

        # Check for missing quantity or rate
        if "qty" not in item:
            raise ValueError(f"Item at index {idx - 1} is missing mandatory key 'qty'.")
        if "rate" not in item:
            raise ValueError(f"Item at index {idx - 1} is missing mandatory key 'rate'.")

        qty_raw = item["qty"]
        rate_raw = item["rate"]

        if qty_raw is None:
            raise ValueError(f"Item at index {idx - 1} has null 'qty'.")
        if rate_raw is None:
            raise ValueError(f"Item at index {idx - 1} has null 'rate'.")

        # Validate Quantity: must be non-negative integer
        try:
            qty = int(qty_raw)
            if qty < 0:
                raise ValueError(f"Item at index {idx - 1} has negative quantity: {qty}.")
        except (ValueError, TypeError) as e:
            if "negative" in str(e):
                raise
            raise ValueError(f"Item at index {idx - 1} has invalid quantity '{qty_raw}'. Must be an integer.")

        # Validate Rate: must be valid non-negative decimal
        try:
            rate = Decimal(str(rate_raw)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if rate < Decimal('0.00'):
                raise ValueError(f"Item at index {idx - 1} has negative rate: {rate}.")
        except (InvalidOperation, ValueError, TypeError) as e:
            if "negative" in str(e):
                raise
            raise ValueError(f"Item at index {idx - 1} has invalid rate '{rate_raw}'. Must be a valid numeric amount.")

        # Line item amount
        item_amount = (Decimal(qty) * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total += item_amount

    return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


if __name__ == '__main__':
    sample_input = [
        {"qty": 2, "rate": 100},
        {"qty": 3, "rate": 50}
    ]
    print(f"Buggy result: {buggy_calculate_total(sample_input)} (Incorrect, expected 350)")
    print(f"Corrected result: {calculate_total(sample_input)} (Correct, equals 350.00)")
