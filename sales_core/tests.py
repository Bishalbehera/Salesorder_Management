"""
Automated Test Suite for Savyant Systems Sales Order & Inventory Management.
Complies with Part 12 of the technical assignment covering all specified scenarios:
1. Order with multiple items and discount -> Correct subtotal and grand total
2. Zero or negative quantity -> Rejected
3. Discount outside 0-20% -> Rejected
4. Confirmation with sufficient stock -> Order confirmed and stock deducted
5. Confirmation with one insufficient-stock item -> No stock or status changes
6. Repeated confirmation -> No additional deduction
7. Cancellation of Confirmed order -> Stock restored once
8. Sales User accesses another user's order -> Access denied
9. CSV containing an invalid row -> No products imported
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from sales_core.models import Product, Customer, SalesOrder, SalesOrderItem, StockMovement
from sales_core.services import OrderService, StockService, CSVImportService, InsufficientStockError

User = get_user_model()


class SalesInventoryTestCase(TestCase):
    def setUp(self):
        # 1. Users
        self.admin_user = User.objects.create_user(
            email='admin@savyant.com',
            password='AdminPassword123',
            name='Admin User',
            role=User.ROLE_ADMIN,
            is_staff=True,
            is_superuser=True
        )

        self.sales_user1 = User.objects.create_user(
            email='sales1@savyant.com',
            password='SalesPassword123',
            name='Sales User 1',
            role=User.ROLE_SALES
        )

        self.sales_user2 = User.objects.create_user(
            email='sales2@savyant.com',
            password='SalesPassword123',
            name='Sales User 2',
            role=User.ROLE_SALES
        )

        # 2. Customers
        self.customer1 = Customer.objects.create(
            name='Customer Alpha',
            email='alpha@example.com',
            mobile='+91-9999999991',
            city='Mumbai',
            is_active=True
        )

        self.customer_inactive = Customer.objects.create(
            name='Customer Inactive',
            email='inactive@example.com',
            mobile='+91-9999999992',
            city='Delhi',
            is_active=False
        )

        # 3. Products
        self.product_keyboard = Product.objects.create(
            product_code='TST-001',
            name='Test Keyboard',
            category='Accessories',
            price=Decimal('1500.00'),
            stock_quantity=10,
            is_active=True
        )

        self.product_mouse = Product.objects.create(
            product_code='TST-002',
            name='Test Mouse',
            category='Accessories',
            price=Decimal('500.00'),
            stock_quantity=20,
            is_active=True
        )

        self.product_low_stock = Product.objects.create(
            product_code='TST-003',
            name='Test Low Stock Item',
            category='Hardware',
            price=Decimal('1000.00'),
            stock_quantity=2,  # Only 2 units available
            is_active=True
        )

        # API & Web test clients
        self.client_sales1 = APIClient()
        self.client_sales1.force_authenticate(user=self.sales_user1)

        self.client_sales2 = APIClient()
        self.client_sales2.force_authenticate(user=self.sales_user2)

        self.client_admin = APIClient()
        self.client_admin.force_authenticate(user=self.admin_user)

    # -------------------------------------------------------------
    # Scenario 1: Order with multiple items and discount
    # Expected: Correct subtotal and grand total
    # Example: 2 x 1500 = 3000, 3 x 500 = 1500 => Subtotal 4500
    # Discount 10% = 450 => Grand Total 4050.00
    # -------------------------------------------------------------
    def test_scenario_01_multiple_items_and_discount(self):
        items_data = [
            {'product_id': self.product_keyboard.id, 'quantity': 2},
            {'product_id': self.product_mouse.id, 'quantity': 3},
        ]
        order = OrderService.create_order(
            user=self.sales_user1,
            customer=self.customer1,
            items_data=items_data,
            discount_percentage=Decimal('10.00')
        )

        self.assertEqual(order.subtotal, Decimal('4500.00'))
        self.assertEqual(order.discount_percentage, Decimal('10.00'))
        self.assertEqual(order.discount_amount, Decimal('450.00'))
        self.assertEqual(order.grand_total, Decimal('4050.00'))
        self.assertEqual(order.status, SalesOrder.STATUS_DRAFT)

        # Check order items snapshot price
        items = list(order.items.all())
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].rate, Decimal('1500.00'))
        self.assertEqual(items[0].amount, Decimal('3000.00'))
        self.assertEqual(items[1].rate, Decimal('500.00'))
        self.assertEqual(items[1].amount, Decimal('1500.00'))

    # -------------------------------------------------------------
    # Scenario 2: Zero or negative quantity
    # Expected: Rejected
    # -------------------------------------------------------------
    def test_scenario_02_zero_or_negative_quantity_rejected(self):
        # Case A: Zero quantity
        with self.assertRaises(ValidationError):
            OrderService.create_order(
                user=self.sales_user1,
                customer=self.customer1,
                items_data=[{'product_id': self.product_keyboard.id, 'quantity': 0}],
                discount_percentage=Decimal('0.00')
            )

        # Case B: Negative quantity
        with self.assertRaises(ValidationError):
            OrderService.create_order(
                user=self.sales_user1,
                customer=self.customer1,
                items_data=[{'product_id': self.product_keyboard.id, 'quantity': -5}],
                discount_percentage=Decimal('0.00')
            )

    # -------------------------------------------------------------
    # Scenario 3: Discount outside 0–20%
    # Expected: Rejected
    # -------------------------------------------------------------
    def test_scenario_03_discount_outside_range_rejected(self):
        items_data = [{'product_id': self.product_keyboard.id, 'quantity': 1}]

        # Case A: Discount > 20%
        with self.assertRaises(ValidationError):
            OrderService.create_order(
                user=self.sales_user1,
                customer=self.customer1,
                items_data=items_data,
                discount_percentage=Decimal('25.00')
            )

        # Case B: Discount < 0%
        with self.assertRaises(ValidationError):
            OrderService.create_order(
                user=self.sales_user1,
                customer=self.customer1,
                items_data=items_data,
                discount_percentage=Decimal('-5.00')
            )

    # -------------------------------------------------------------
    # Scenario 4: Confirmation with sufficient stock
    # Expected: Order confirmed and stock deducted
    # -------------------------------------------------------------
    def test_scenario_04_confirmation_with_sufficient_stock(self):
        initial_stock = self.product_keyboard.stock_quantity  # 10
        order = OrderService.create_order(
            user=self.sales_user1,
            customer=self.customer1,
            items_data=[{'product_id': self.product_keyboard.id, 'quantity': 3}],
            discount_percentage=Decimal('0.00')
        )

        confirmed_order = OrderService.confirm_order(order.id, self.sales_user1)
        self.assertEqual(confirmed_order.status, SalesOrder.STATUS_CONFIRMED)

        # Refresh product from DB
        self.product_keyboard.refresh_from_db()
        self.assertEqual(self.product_keyboard.stock_quantity, initial_stock - 3)

        # Check stock movement record was created
        movement = StockMovement.objects.filter(related_order=order).first()
        self.assertIsNotNone(movement)
        self.assertEqual(movement.movement_type, StockMovement.TYPE_ORDER_CONFIRM)
        self.assertEqual(movement.quantity_change, -3)

    # -------------------------------------------------------------
    # Scenario 5: Confirmation with one insufficient-stock item
    # Expected: No stock or status changes (entire order rejected)
    # -------------------------------------------------------------
    def test_scenario_05_confirmation_with_insufficient_stock_rejected(self):
        initial_keyboard_stock = self.product_keyboard.stock_quantity  # 10
        initial_low_stock = self.product_low_stock.stock_quantity      # 2

        # Order requesting 2 keyboards (sufficient) and 5 low_stock_items (insufficient, only 2 exist)
        order = OrderService.create_order(
            user=self.sales_user1,
            customer=self.customer1,
            items_data=[
                {'product_id': self.product_keyboard.id, 'quantity': 2},
                {'product_id': self.product_low_stock.id, 'quantity': 5},
            ],
            discount_percentage=Decimal('0.00')
        )

        with self.assertRaises(InsufficientStockError):
            OrderService.confirm_order(order.id, self.sales_user1)

        # Verify atomic rollback: Order must remain Draft
        order.refresh_from_db()
        self.assertEqual(order.status, SalesOrder.STATUS_DRAFT)

        # Verify NO stock was deducted for ANY product
        self.product_keyboard.refresh_from_db()
        self.product_low_stock.refresh_from_db()
        self.assertEqual(self.product_keyboard.stock_quantity, initial_keyboard_stock)
        self.assertEqual(self.product_low_stock.stock_quantity, initial_low_stock)

        # No movement records created
        self.assertFalse(StockMovement.objects.filter(related_order=order).exists())

    # -------------------------------------------------------------
    # Scenario 6: Repeated confirmation
    # Expected: No additional deduction (idempotent)
    # -------------------------------------------------------------
    def test_scenario_06_repeated_confirmation_idempotent(self):
        initial_stock = self.product_keyboard.stock_quantity  # 10
        order = OrderService.create_order(
            user=self.sales_user1,
            customer=self.customer1,
            items_data=[{'product_id': self.product_keyboard.id, 'quantity': 4}],
            discount_percentage=Decimal('0.00')
        )

        # First confirmation
        OrderService.confirm_order(order.id, self.sales_user1)
        self.product_keyboard.refresh_from_db()
        self.assertEqual(self.product_keyboard.stock_quantity, initial_stock - 4)
        movements_count_first = StockMovement.objects.filter(related_order=order).count()
        self.assertEqual(movements_count_first, 1)

        # Second confirmation attempt
        OrderService.confirm_order(order.id, self.sales_user1)
        self.product_keyboard.refresh_from_db()
        # Stock must NOT be deducted again!
        self.assertEqual(self.product_keyboard.stock_quantity, initial_stock - 4)
        self.assertEqual(StockMovement.objects.filter(related_order=order).count(), movements_count_first)

    # -------------------------------------------------------------
    # Scenario 7: Cancellation of Confirmed order
    # Expected: Stock restored once
    # -------------------------------------------------------------
    def test_scenario_07_cancellation_of_confirmed_order_restores_stock_once(self):
        initial_stock = self.product_keyboard.stock_quantity  # 10
        order = OrderService.create_order(
            user=self.sales_user1,
            customer=self.customer1,
            items_data=[{'product_id': self.product_keyboard.id, 'quantity': 4}],
            discount_percentage=Decimal('0.00')
        )

        OrderService.confirm_order(order.id, self.sales_user1)
        self.product_keyboard.refresh_from_db()
        self.assertEqual(self.product_keyboard.stock_quantity, initial_stock - 4)

        # Cancel confirmed order
        OrderService.cancel_order(order.id, self.sales_user1)
        order.refresh_from_db()
        self.assertEqual(order.status, SalesOrder.STATUS_CANCELLED)

        # Stock must be restored
        self.product_keyboard.refresh_from_db()
        self.assertEqual(self.product_keyboard.stock_quantity, initial_stock)

        # Check restoration stock movement
        cancel_movement = StockMovement.objects.filter(
            related_order=order,
            movement_type=StockMovement.TYPE_ORDER_CANCEL
        ).first()
        self.assertIsNotNone(cancel_movement)
        self.assertEqual(cancel_movement.quantity_change, 4)

        # Repeated cancellation attempt should not restore again
        OrderService.cancel_order(order.id, self.sales_user1)
        self.product_keyboard.refresh_from_db()
        self.assertEqual(self.product_keyboard.stock_quantity, initial_stock)
        self.assertEqual(
            StockMovement.objects.filter(related_order=order, movement_type=StockMovement.TYPE_ORDER_CANCEL).count(),
            1
        )

    # -------------------------------------------------------------
    # Scenario 8: Sales User accesses another user's order
    # Expected: Access denied (HTTP 403 Forbidden)
    # -------------------------------------------------------------
    def test_scenario_08_sales_user_cannot_access_other_user_order(self):
        # Order created by Sales User 1
        order_user1 = OrderService.create_order(
            user=self.sales_user1,
            customer=self.customer1,
            items_data=[{'product_id': self.product_keyboard.id, 'quantity': 1}],
            discount_percentage=Decimal('0.00')
        )

        # Sales User 2 attempts to access via REST API
        url = reverse('api_order_detail', kwargs={'pk': order_user1.id})
        response = self.client_sales2.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Sales User 2 attempts to confirm user 1's order via REST API
        confirm_url = reverse('api_order_confirm', kwargs={'pk': order_user1.id})
        confirm_resp = self.client_sales2.post(confirm_url)
        self.assertEqual(confirm_resp.status_code, status.HTTP_403_FORBIDDEN)

        # Sales User 2 attempts to access via Web UI view
        web_client = Client()
        web_client.force_login(self.sales_user2)
        web_resp = web_client.get(reverse('order_detail', kwargs={'pk': order_user1.id}))
        self.assertEqual(web_resp.status_code, 403)

        # However, Admin user CAN access any order
        admin_resp = self.client_admin.get(url)
        self.assertEqual(admin_resp.status_code, status.HTTP_200_OK)

    # -------------------------------------------------------------
    # Scenario 9: CSV containing an invalid row
    # Expected: No products imported (all-or-nothing rollback)
    # -------------------------------------------------------------
    def test_scenario_09_csv_invalid_row_imports_nothing(self):
        initial_product_count = Product.objects.count()

        invalid_csv_content = (
            "product_code,product_name,category,price,stock_quantity,status\n"
            "VAL-001,Valid Product,Accessories,1000.00,10,Active\n"
            "INV-002,Negative Price Product,Accessories,-500.00,10,Active\n"  # Invalid negative price!
        )

        success, count, errors = CSVImportService.import_products_csv(invalid_csv_content, self.admin_user)

        self.assertFalse(success)
        self.assertEqual(count, 0)
        self.assertTrue(len(errors) > 0)
        self.assertEqual(errors[0]['row'], 3)
        self.assertIn("cannot be negative", errors[0]['error'])

        # Verify nothing was imported to database (not even VAL-001)
        self.assertEqual(Product.objects.count(), initial_product_count)
        self.assertFalse(Product.objects.filter(product_code='VAL-001').exists())

    # -------------------------------------------------------------
    # Additional Scenario: Valid CSV Import
    # -------------------------------------------------------------
    def test_valid_csv_import_success(self):
        initial_product_count = Product.objects.count()

        valid_csv = (
            "product_code,product_name,category,price,stock_quantity,status\n"
            "NEW-001,Wireless Keyboard,Accessories,1200.00,25,Active\n"
            "NEW-002,Silent Click Mouse,Accessories,450.00,40,Active\n"
        )

        success, count, errors = CSVImportService.import_products_csv(valid_csv, self.admin_user)
        self.assertTrue(success)
        self.assertEqual(count, 2)
        self.assertEqual(len(errors), 0)
        self.assertEqual(Product.objects.count(), initial_product_count + 2)

        # Verify opening stock movement created
        prod = Product.objects.get(product_code='NEW-001')
        self.assertEqual(prod.stock_quantity, 25)
        self.assertTrue(StockMovement.objects.filter(product=prod, movement_type=StockMovement.TYPE_OPENING).exists())

    # -------------------------------------------------------------
    # Additional Scenario: Safe deletion prevents deleting customer or product with orders
    # -------------------------------------------------------------
    def test_safe_deletion_rules(self):
        order = OrderService.create_order(
            user=self.sales_user1,
            customer=self.customer1,
            items_data=[{'product_id': self.product_keyboard.id, 'quantity': 1}],
            discount_percentage=Decimal('0.00')
        )

        # Customer referenced by order cannot be deleted
        self.assertFalse(self.customer1.can_delete())
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.customer1.delete()

        # Product referenced by order cannot be deleted
        self.assertFalse(self.product_keyboard.can_delete())
        with self.assertRaises(ProtectedError):
            self.product_keyboard.delete()
