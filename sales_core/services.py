"""
Business logic and domain services for Sales Order & Inventory Management.
Handles atomic transactions, concurrency locks, stock updates, calculations, and CSV parsing.
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import csv
import io
from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from .models import Product, Customer, SalesOrder, SalesOrderItem, StockMovement, User


class InsufficientStockError(Exception):
    """Raised when an order confirmation cannot be fulfilled due to low stock."""
    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details or []


class OrderService:
    @staticmethod
    def calculate_order_values(items_data, discount_percentage):
        """
        Pure calculation helper for unit-testing and validation.
        Formula:
        Item Amount = Quantity * Rate
        Subtotal = Sum of Item Amounts
        Discount Amount = Subtotal * Discount Percentage / 100
        Grand Total = Subtotal - Discount Amount
        All monetary amounts rounded to 2 decimal places.
        """
        discount_pct = Decimal(str(discount_percentage or '0.00'))
        if discount_pct < Decimal('0.00') or discount_pct > Decimal('20.00'):
            raise ValidationError("Discount percentage must be strictly between 0 and 20.")

        subtotal = Decimal('0.00')
        calculated_items = []

        for item in items_data:
            qty = int(item['quantity'])
            if qty <= 0:
                raise ValidationError("Product quantity must be a positive whole number greater than 0.")
            rate = Decimal(str(item['rate'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if rate < Decimal('0.00'):
                raise ValidationError("Product rate cannot be negative.")
            item_amt = (Decimal(qty) * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            subtotal += item_amt
            calculated_items.append({
                'product_id': item['product_id'],
                'quantity': qty,
                'rate': rate,
                'amount': item_amt
            })

        subtotal = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        discount_amount = (subtotal * discount_pct / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        grand_total = (subtotal - discount_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        return {
            'subtotal': subtotal,
            'discount_percentage': discount_pct,
            'discount_amount': discount_amount,
            'grand_total': grand_total,
            'items': calculated_items
        }

    @classmethod
    def create_order(cls, user, customer, items_data, discount_percentage=Decimal('0.00')):
        """
        Creates a new Draft sales order.
        Fetches the current price of each active product as the order item rate.
        Never trusts client rate, totals, or status.
        """
        if not customer.is_active:
            raise ValidationError(f"Customer '{customer.name}' is inactive and cannot place orders.")

        if not items_data or len(items_data) == 0:
            raise ValidationError("An order must contain at least one product item.")

        # Check for duplicate products in the submitted items
        product_ids = [item['product_id'] for item in items_data]
        if len(product_ids) != len(set(product_ids)):
            raise ValidationError("Duplicate products within the same order are not allowed.")

        # Fetch active products and their current prices
        products = Product.objects.filter(id__in=product_ids)
        product_map = {p.id: p for p in products}

        if len(product_map) != len(product_ids):
            raise ValidationError("One or more selected products do not exist.")

        prepared_items = []
        for item in items_data:
            product = product_map[item['product_id']]
            if not product.is_active:
                raise ValidationError(f"Product '{product.name}' is inactive and cannot be ordered.")
            
            qty = int(item.get('quantity', 0))
            if qty <= 0:
                raise ValidationError(f"Quantity for product '{product.name}' must be at least 1.")

            # Always fetch the product's current active price from database
            rate = product.price
            prepared_items.append({
                'product_id': product.id,
                'quantity': qty,
                'rate': rate,
            })

        calc_result = cls.calculate_order_values(prepared_items, discount_percentage)

        with transaction.atomic():
            order_number = SalesOrder.generate_unique_order_number()
            order = SalesOrder.objects.create(
                order_number=order_number,
                customer=customer,
                order_date=timezone.now().date(),
                status=SalesOrder.STATUS_DRAFT,
                discount_percentage=calc_result['discount_percentage'],
                subtotal=calc_result['subtotal'],
                discount_amount=calc_result['discount_amount'],
                grand_total=calc_result['grand_total'],
                created_by=user
            )

            for item in calc_result['items']:
                product = product_map[item['product_id']]
                SalesOrderItem.objects.create(
                    sales_order=order,
                    product=product,
                    quantity=item['quantity'],
                    rate=item['rate'],
                    amount=item['amount']
                )

        return order

    @classmethod
    def confirm_order(cls, order_id, user):
        """
        Confirms a Draft order:
        - Locks product rows using select_for_update() to prevent race conditions & negative stock.
        - Checks stock availability for ALL products in order.
        - If ANY product has insufficient stock, rejects the entire confirmation (atomic rollback).
        - Deducts stock, creates StockMovement records, sets status to 'confirmed'.
        - Idempotent: Repeated confirmation requests do not deduct stock again.
        """
        with transaction.atomic():
            # Lock the order row
            order = SalesOrder.objects.select_for_update().get(id=order_id)

            # Check permissions
            if not user.is_admin_user and order.created_by != user:
                raise PermissionDenied("You do not have permission to confirm this order.")

            if order.status == SalesOrder.STATUS_CONFIRMED:
                return order  # Already confirmed, do not deduct stock again

            if order.status == SalesOrder.STATUS_CANCELLED:
                raise ValidationError("Cancelled orders cannot be confirmed.")

            # Lock product rows in deterministic order to prevent deadlocks
            items = list(order.items.select_related('product').all())
            product_ids = sorted([item.product_id for item in items])
            
            locked_products = {
                p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids)
            }

            # Check stock for all items
            insufficient_items = []
            for item in items:
                p = locked_products[item.product_id]
                if p.stock_quantity < item.quantity:
                    insufficient_items.append({
                        'product_code': p.product_code,
                        'product_name': p.name,
                        'available': p.stock_quantity,
                        'required': item.quantity
                    })

            if insufficient_items:
                reasons = [
                    f"{it['product_code']} ({it['product_name']}): available {it['available']}, required {it['required']}"
                    for it in insufficient_items
                ]
                raise InsufficientStockError(
                    f"Insufficient stock for: {', '.join(reasons)}. Entire confirmation rejected.",
                    details=insufficient_items
                )

            # Deduct stock and record movements
            for item in items:
                p = locked_products[item.product_id]
                p.stock_quantity -= item.quantity
                p.save(update_fields=['stock_quantity', 'updated_at'])

                StockMovement.objects.create(
                    product=p,
                    movement_type=StockMovement.TYPE_ORDER_CONFIRM,
                    quantity_change=-item.quantity,
                    related_order=order,
                    reason=f"Order {order.order_number} confirmed by {user.name}",
                    created_by=user
                )

            order.status = SalesOrder.STATUS_CONFIRMED
            order.save(update_fields=['status', 'updated_at'])

        return order

    @classmethod
    def cancel_order(cls, order_id, user):
        """
        Cancels an order:
        - Reachable from Draft or Confirmed.
        - If order was Draft: transition to Cancelled, no stock effect.
        - If order was Confirmed: transition to Cancelled, restore deducted stock, record StockMovement.
        - Idempotent: Repeated cancellation requests do not restore stock again.
        - Cancelled orders are read-only.
        """
        with transaction.atomic():
            order = SalesOrder.objects.select_for_update().get(id=order_id)

            if not user.is_admin_user and order.created_by != user:
                raise PermissionDenied("You do not have permission to cancel this order.")

            if order.status == SalesOrder.STATUS_CANCELLED:
                return order  # Already cancelled, idempotent

            prev_status = order.status

            if prev_status == SalesOrder.STATUS_CONFIRMED:
                # Restore stock for each item
                items = list(order.items.select_related('product').all())
                product_ids = sorted([item.product_id for item in items])
                locked_products = {
                    p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids)
                }

                for item in items:
                    p = locked_products[item.product_id]
                    p.stock_quantity += item.quantity
                    p.save(update_fields=['stock_quantity', 'updated_at'])

                    StockMovement.objects.create(
                        product=p,
                        movement_type=StockMovement.TYPE_ORDER_CANCEL,
                        quantity_change=item.quantity,
                        related_order=order,
                        reason=f"Order {order.order_number} cancelled by {user.name} - stock restored",
                        created_by=user
                    )

            order.status = SalesOrder.STATUS_CANCELLED
            order.save(update_fields=['status', 'updated_at'])

        return order


class StockService:
    @staticmethod
    def adjust_stock(product_id, quantity_change, reason, user):
        """
        Allows Admin to increase or decrease stock with a mandatory reason.
        Rejects adjustments that would make stock negative.
        Creates a stock movement record.
        """
        if not user.is_admin_user:
            raise PermissionDenied("Only Admin users are authorized to adjust stock.")

        if not reason or not reason.strip():
            raise ValidationError("A mandatory reason must be provided for stock adjustment.")

        qty_change = int(quantity_change)
        if qty_change == 0:
            raise ValidationError("Quantity change cannot be zero.")

        with transaction.atomic():
            product = Product.objects.select_for_update().get(id=product_id)
            new_stock = product.stock_quantity + qty_change

            if new_stock < 0:
                raise ValidationError(
                    f"Adjustment of {qty_change:+d} rejected: current stock is {product.stock_quantity}, resulting stock cannot be negative ({new_stock})."
                )

            product.stock_quantity = new_stock
            product.save(update_fields=['stock_quantity', 'updated_at'])

            movement = StockMovement.objects.create(
                product=product,
                movement_type=StockMovement.TYPE_ADJUSTMENT,
                quantity_change=qty_change,
                related_order=None,
                reason=reason.strip(),
                created_by=user
            )

        return product, movement


class CSVImportService:
    EXPECTED_COLUMNS = ['product_code', 'product_name', 'category', 'price', 'stock_quantity', 'status']

    @classmethod
    def import_products_csv(cls, file_content, user):
        """
        Admin-only product import with all-or-nothing validation.
        Format: product_code,product_name,category,price,stock_quantity,status
        - Validates header and each row.
        - Rejects duplicate codes within the CSV and existing codes in DB.
        - Rejects negative prices, negative stock, and invalid statuses.
        - If ANY row is invalid, imports NOTHING.
        - If valid, records opening stock as StockMovement.
        Returns: (success: bool, imported_count: int, errors: list of {row, error})
        """
        if not user.is_admin_user:
            raise PermissionDenied("Only Admin users are authorized to import products.")

        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8-sig', errors='replace')

        reader = csv.reader(io.StringIO(file_content.strip()))
        rows = list(reader)

        if not rows:
            return False, 0, [{"row": 1, "error": "CSV file is completely empty."}]

        header = [col.strip().lower() for col in rows[0]]
        if header != cls.EXPECTED_COLUMNS:
            return False, 0, [{
                "row": 1,
                "error": f"Invalid header columns. Expected: {','.join(cls.EXPECTED_COLUMNS)}, but received: {','.join(header)}"
            }]

        errors = []
        parsed_products = []
        codes_in_file = set()

        # Pre-fetch existing product codes from database to avoid N queries
        existing_codes = set(Product.objects.values_list('product_code', flat=True))

        for idx, row in enumerate(rows[1:], start=2):
            if not row or all(not cell.strip() for cell in row):
                continue  # skip completely empty lines

            if len(row) != len(cls.EXPECTED_COLUMNS):
                errors.append({
                    "row": idx,
                    "error": f"Row has {len(row)} columns, expected {len(cls.EXPECTED_COLUMNS)}."
                })
                continue

            code, name, category, price_str, stock_str, status_str = [cell.strip() for cell in row]

            # 1. Product code validation
            if not code:
                errors.append({"row": idx, "error": "Product code cannot be empty."})
            elif code in codes_in_file:
                errors.append({"row": idx, "error": f"Duplicate product code '{code}' within the CSV file."})
            elif code in existing_codes:
                errors.append({"row": idx, "error": f"Product code '{code}' already exists in the database."})
            codes_in_file.add(code)

            # 2. Product name validation
            if not name:
                errors.append({"row": idx, "error": "Product name cannot be empty."})

            # 3. Category validation
            if not category:
                errors.append({"row": idx, "error": "Category cannot be empty."})

            # 4. Price validation
            price_val = None
            try:
                price_val = Decimal(price_str)
                if price_val < Decimal('0.00'):
                    errors.append({"row": idx, "error": f"Price '{price_str}' cannot be negative."})
            except (InvalidOperation, ValueError):
                errors.append({"row": idx, "error": f"Price '{price_str}' is not a valid decimal number."})

            # 5. Stock quantity validation
            stock_val = None
            try:
                stock_val = int(stock_str)
                if stock_val < 0:
                    errors.append({"row": idx, "error": f"Stock quantity '{stock_str}' cannot be negative."})
            except ValueError:
                errors.append({"row": idx, "error": f"Stock quantity '{stock_str}' is not a valid whole integer."})

            # 6. Status validation
            status_clean = status_str.capitalize()
            if status_clean not in ('Active', 'Inactive'):
                errors.append({"row": idx, "error": f"Status '{status_str}' is invalid. Allowed values: 'Active' or 'Inactive'."})
            is_active = (status_clean == 'Active')

            if not errors:
                parsed_products.append({
                    'product_code': code,
                    'name': name,
                    'category': category,
                    'price': price_val,
                    'stock_quantity': stock_val,
                    'is_active': is_active
                })

        # All-or-nothing check: If any error occurred, import nothing!
        if errors:
            return False, 0, errors

        # Atomic database insertion
        with transaction.atomic():
            for item in parsed_products:
                prod = Product.objects.create(
                    product_code=item['product_code'],
                    name=item['name'],
                    category=item['category'],
                    price=item['price'],
                    stock_quantity=item['stock_quantity'],
                    is_active=item['is_active']
                )

                # Record opening stock as stock movement
                if prod.stock_quantity > 0:
                    StockMovement.objects.create(
                        product=prod,
                        movement_type=StockMovement.TYPE_OPENING,
                        quantity_change=prod.stock_quantity,
                        related_order=None,
                        reason="CSV Import opening stock",
                        created_by=user
                    )

        return True, len(parsed_products), []
