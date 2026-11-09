"""
Sample data seed script for Savyant Systems Sales Order & Inventory Management.
Creates sample Admin & Sales users, sample customers, products, and initial stock movements.
Run using: python seed_data.py
"""

import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sales_inventory_project.settings')
django.setup()

from sales_core.models import User, Customer, Product, SalesOrder, SalesOrderItem, StockMovement
from sales_core.services import OrderService


def seed_database():
    print("Seeding database with sample users, customers, products and orders...")

    # 1. Users
    admin_user, created = User.objects.get_or_create(
        email='admin@savyant.com',
        defaults={
            'username': 'admin@savyant.com',
            'name': 'System Administrator',
            'role': User.ROLE_ADMIN,
            'is_staff': True,
            'is_superuser': True
        }
    )
    if created:
        admin_user.set_password('Admin@123')
        admin_user.save()
        print("Created Admin user: admin@savyant.com / Admin@123")

    sales_user1, created = User.objects.get_or_create(
        email='sales1@savyant.com',
        defaults={
            'username': 'sales1@savyant.com',
            'name': 'Rahul Sharma (Sales)',
            'role': User.ROLE_SALES,
        }
    )
    if created:
        sales_user1.set_password('Sales@123')
        sales_user1.save()
        print("Created Sales User 1: sales1@savyant.com / Sales@123")

    sales_user2, created = User.objects.get_or_create(
        email='sales2@savyant.com',
        defaults={
            'username': 'sales2@savyant.com',
            'name': 'Priya Patel (Sales)',
            'role': User.ROLE_SALES,
        }
    )
    if created:
        sales_user2.set_password('Sales@123')
        sales_user2.save()
        print("Created Sales User 2: sales2@savyant.com / Sales@123")

    # 2. Customers
    customers_data = [
        {'name': 'Apex Enterprises', 'email': 'contact@apex.com', 'mobile': '+91-9876543210', 'city': 'Mumbai', 'is_active': True},
        {'name': 'Bharat Tech Traders', 'email': 'sales@bharattech.in', 'mobile': '+91-9876543211', 'city': 'Delhi', 'is_active': True},
        {'name': 'Crestline Solutions', 'email': 'info@crestline.org', 'mobile': '+91-9876543212', 'city': 'Bengaluru', 'is_active': True},
        {'name': 'Delta Hardware Store', 'email': 'orders@deltahw.com', 'mobile': '+91-9876543213', 'city': 'Pune', 'is_active': True},
        {'name': 'Echo Digital Corp', 'email': 'support@echodigital.in', 'mobile': '+91-9876543214', 'city': 'Hyderabad', 'is_active': False},
        {'name': 'Zenith Inactive Client', 'email': 'dormant@zenith.com', 'mobile': '+91-9876543215', 'city': 'Chennai', 'is_active': False},
    ]

    customers = {}
    for c_data in customers_data:
        cust, _ = Customer.objects.get_or_create(email=c_data['email'], defaults=c_data)
        customers[cust.name] = cust
    print(f"Loaded {len(customers)} customers.")

    # 3. Products
    products_data = [
        {'product_code': 'PRD-001', 'name': 'Mechanical Keyboard', 'category': 'Accessories', 'price': Decimal('1500.00'), 'stock_quantity': 35, 'is_active': True},
        {'product_code': 'PRD-002', 'name': 'Optical Mouse', 'category': 'Accessories', 'price': Decimal('500.00'), 'stock_quantity': 60, 'is_active': True},
        {'product_code': 'PRD-003', 'name': 'USB-C Multiport Hub', 'category': 'Cables & Adapters', 'price': Decimal('1200.00'), 'stock_quantity': 20, 'is_active': True},
        {'product_code': 'PRD-004', 'name': '27-inch IPS Monitor', 'category': 'Displays', 'price': Decimal('18500.00'), 'stock_quantity': 8, 'is_active': True},
        {'product_code': 'PRD-005', 'name': 'Wireless Noise-Canceling Headset', 'category': 'Audio', 'price': Decimal('3200.00'), 'stock_quantity': 5, 'is_active': True},
        {'product_code': 'PRD-006', 'name': 'Desk Mat XL', 'category': 'Accessories', 'price': Decimal('650.00'), 'stock_quantity': 45, 'is_active': True},
        {'product_code': 'PRD-007', 'name': 'Legacy VGA Cable', 'category': 'Cables & Adapters', 'price': Decimal('200.00'), 'stock_quantity': 0, 'is_active': False},
    ]

    products = {}
    for p_data in products_data:
        stock = p_data.pop('stock_quantity')
        prod, created = Product.objects.get_or_create(product_code=p_data['product_code'], defaults={**p_data, 'stock_quantity': stock})
        if created and stock > 0:
            StockMovement.objects.create(
                product=prod,
                movement_type=StockMovement.TYPE_OPENING,
                quantity_change=stock,
                reason="Initial Opening Stock",
                created_by=admin_user
            )
        products[prod.product_code] = prod
    print(f"Loaded {len(products)} products and recorded opening stock movements.")

    # 4. Sample Orders
    if not SalesOrder.objects.exists():
        # Order 1: Confirmed order with multiple items and discount
        order1 = OrderService.create_order(
            user=sales_user1,
            customer=customers['Apex Enterprises'],
            items_data=[
                {'product_id': products['PRD-001'].id, 'quantity': 2},
                {'product_id': products['PRD-002'].id, 'quantity': 3},
            ],
            discount_percentage=Decimal('10.00')
        )
        OrderService.confirm_order(order1.id, sales_user1)
        print(f"Created & Confirmed Order: {order1.order_number} (Grand Total: {order1.grand_total})")

        # Order 2: Another Confirmed order for Bharat Tech Traders
        order2 = OrderService.create_order(
            user=sales_user2,
            customer=customers['Bharat Tech Traders'],
            items_data=[
                {'product_id': products['PRD-004'].id, 'quantity': 1},
                {'product_id': products['PRD-003'].id, 'quantity': 2},
            ],
            discount_percentage=Decimal('5.00')
        )
        OrderService.confirm_order(order2.id, sales_user2)
        print(f"Created & Confirmed Order: {order2.order_number} (Grand Total: {order2.grand_total})")

        # Order 3: Draft order for Crestline Solutions
        order3 = OrderService.create_order(
            user=sales_user1,
            customer=customers['Crestline Solutions'],
            items_data=[
                {'product_id': products['PRD-006'].id, 'quantity': 5},
                {'product_id': products['PRD-002'].id, 'quantity': 2},
            ],
            discount_percentage=Decimal('0.00')
        )
        print(f"Created Draft Order: {order3.order_number}")

        # Order 4: Cancelled order (previously confirmed, then cancelled to demonstrate stock restore)
        order4 = OrderService.create_order(
            user=sales_user2,
            customer=customers['Delta Hardware Store'],
            items_data=[
                {'product_id': products['PRD-005'].id, 'quantity': 1},
            ],
            discount_percentage=Decimal('0.00')
        )
        OrderService.confirm_order(order4.id, sales_user2)
        OrderService.cancel_order(order4.id, sales_user2)
        print(f"Created and Cancelled Order: {order4.order_number}")

    print("Database seeding completed successfully!")


if __name__ == '__main__':
    seed_database()
