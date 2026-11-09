"""
Unit tests for Part 11: Debugging Exercise
Tests the corrected calculate_total function against all edge cases:
- Normal items calculation matching 350
- Empty list and None behavior
- Missing 'qty' or 'rate' keys
- Negative quantities and rates
- Non-numeric inputs
"""

import unittest
from decimal import Decimal
from debugging_exercise import calculate_total, buggy_calculate_total


class TestCalculateTotal(unittest.TestCase):
    def test_sample_case_from_assignment(self):
        """Verify the exact problem input returns 350.00"""
        items = [
            {"qty": 2, "rate": 100},
            {"qty": 3, "rate": 50}
        ]
        # Buggy returns 150
        self.assertEqual(buggy_calculate_total(items), 150)
        # Corrected returns 350.00
        self.assertEqual(calculate_total(items), Decimal('350.00'))

    def test_empty_list_and_none(self):
        """Empty list or None should return Decimal('0.00') without errors"""
        self.assertEqual(calculate_total([]), Decimal('0.00'))
        self.assertEqual(calculate_total(None), Decimal('0.00'))

    def test_decimal_rounding(self):
        """Ensures accurate monetary decimal math with standard rounding"""
        items = [
            {"qty": 3, "rate": "19.99"},
            {"qty": 2, "rate": "10.05"},
        ]
        # (3 * 19.99 = 59.97) + (2 * 10.05 = 20.10) = 80.07
        self.assertEqual(calculate_total(items), Decimal('80.07'))

    def test_missing_qty_key(self):
        """Raises ValueError when 'qty' is missing"""
        items = [{"rate": 100}]
        with self.assertRaises(ValueError) as ctx:
            calculate_total(items)
        self.assertIn("missing mandatory key 'qty'", str(ctx.exception))

    def test_missing_rate_key(self):
        """Raises ValueError when 'rate' is missing"""
        items = [{"qty": 5}]
        with self.assertRaises(ValueError) as ctx:
            calculate_total(items)
        self.assertIn("missing mandatory key 'rate'", str(ctx.exception))

    def test_negative_quantity(self):
        """Raises ValueError when quantity is negative"""
        items = [{"qty": -2, "rate": 100}]
        with self.assertRaises(ValueError) as ctx:
            calculate_total(items)
        self.assertIn("negative", str(ctx.exception).lower())

    def test_negative_rate(self):
        """Raises ValueError when rate is negative"""
        items = [{"qty": 2, "rate": -50}]
        with self.assertRaises(ValueError) as ctx:
            calculate_total(items)
        self.assertIn("negative", str(ctx.exception).lower())

    def test_non_numeric_input(self):
        """Raises ValueError when quantity or rate is non-numeric"""
        with self.assertRaises(ValueError):
            calculate_total([{"qty": "abc", "rate": 100}])

        with self.assertRaises(ValueError):
            calculate_total([{"qty": 2, "rate": "xyz"}])


if __name__ == '__main__':
    unittest.main()
