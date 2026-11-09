"""
Web Views for Sales Order & Inventory Management System.
Enforces role-based permissions, transactional updates, reports, and UI actions.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Sum, Count, Q, F, DecimalField, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.http import HttpResponseForbidden, JsonResponse
from decimal import Decimal, ROUND_HALF_UP

from .models import User, Customer, Product, SalesOrder, SalesOrderItem, StockMovement
from .services import OrderService, StockService, CSVImportService, InsufficientStockError


def admin_required(view_func):
    """Decorator ensuring that only Admin users can access the view."""
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_admin_user:
            messages.error(request, "Access denied. Administrator privileges are required.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


# ==========================================
# Authentication Views
# ==========================================

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.name} ({user.get_role_display()})!")
            next_url = request.GET.get('next')
            return redirect(next_url if next_url else 'dashboard')
        else:
            messages.error(request, "Invalid email address or password.")

    return render(request, 'auth/login.html')


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('login')


# ==========================================
# Dashboard View
# ==========================================

@login_required
def dashboard_view(request):
    user = request.user
    orders_base = SalesOrder.objects.all() if user.is_admin_user else SalesOrder.objects.filter(created_by=user)

    total_orders = orders_base.count()
    draft_orders = orders_base.filter(status=SalesOrder.STATUS_DRAFT).count()
    confirmed_orders = orders_base.filter(status=SalesOrder.STATUS_CONFIRMED).count()
    total_sales = orders_base.filter(status=SalesOrder.STATUS_CONFIRMED).aggregate(
        total=Coalesce(Sum('grand_total'), Decimal('0.00'))
    )['total']

    low_stock_count = Product.objects.filter(stock_quantity__lt=10, is_active=True).count()
    recent_orders = orders_base.select_related('customer', 'created_by')[:6]

    context = {
        'total_orders': total_orders,
        'draft_orders': draft_orders,
        'confirmed_orders': confirmed_orders,
        'total_sales': total_sales,
        'low_stock_count': low_stock_count,
        'recent_orders': recent_orders,
    }
    return render(request, 'dashboard.html', context)


# ==========================================
# Customer Management Views
# ==========================================

@login_required
def customer_list(request):
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')

    # Sales user can view active customers only, unless admin
    queryset = Customer.objects.all() if request.user.is_admin_user else Customer.objects.filter(is_active=True)

    if search_query:
        queryset = queryset.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(mobile__icontains=search_query)
        )

    if request.user.is_admin_user and status_filter in ('active', 'inactive'):
        queryset = queryset.filter(is_active=(status_filter == 'active'))

    context = {
        'customers': queryset,
        'search_query': search_query,
        'status_filter': status_filter,
    }
    return render(request, 'customers/customer_list.html', context)


@login_required
@admin_required
def customer_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        mobile = request.POST.get('mobile', '').strip()
        city = request.POST.get('city', '').strip()
        is_active = request.POST.get('is_active') == 'on'

        if not name or not email or not mobile:
            messages.error(request, "Name, email, and mobile are required fields.")
        else:
            customer = Customer.objects.create(
                name=name,
                email=email,
                mobile=mobile,
                city=city,
                is_active=is_active
            )
            messages.success(request, f"Customer '{customer.name}' created successfully.")
            return redirect('customer_list')

    return render(request, 'customers/customer_form.html', {'action': 'Create'})


@login_required
@admin_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        mobile = request.POST.get('mobile', '').strip()
        city = request.POST.get('city', '').strip()
        is_active = request.POST.get('is_active') == 'on'

        if not name or not email or not mobile:
            messages.error(request, "Name, email, and mobile are required fields.")
        else:
            customer.name = name
            customer.email = email
            customer.mobile = mobile
            customer.city = city
            customer.is_active = is_active
            customer.save()
            messages.success(request, f"Customer '{customer.name}' updated successfully.")
            return redirect('customer_list')

    return render(request, 'customers/customer_form.html', {'customer': customer, 'action': 'Edit'})


@login_required
@admin_required
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    if not customer.can_delete():
        messages.error(
            request,
            f"Cannot delete customer '{customer.name}' because existing orders reference this customer. You can deactivate the customer instead."
        )
        return redirect('customer_list')

    if request.method == 'POST':
        name = customer.name
        customer.delete()
        messages.success(request, f"Customer '{name}' deleted successfully.")
        return redirect('customer_list')

    return render(request, 'customers/customer_confirm_delete.html', {'customer': customer})


@login_required
@admin_required
def customer_toggle_status(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    customer.is_active = not customer.is_active
    customer.save(update_fields=['is_active'])
    status_str = "activated" if customer.is_active else "deactivated"
    messages.success(request, f"Customer '{customer.name}' {status_str} successfully.")
    return redirect('customer_list')


# ==========================================
# Product Management Views
# ==========================================

@login_required
def product_list(request):
    search_query = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '').strip()
    status_filter = request.GET.get('status', 'all')

    queryset = Product.objects.all() if request.user.is_admin_user else Product.objects.filter(is_active=True)

    if search_query:
        queryset = queryset.filter(
            Q(product_code__icontains=search_query) |
            Q(name__icontains=search_query)
        )

    if category_filter:
        queryset = queryset.filter(category=category_filter)

    if request.user.is_admin_user and status_filter in ('active', 'inactive'):
        queryset = queryset.filter(is_active=(status_filter == 'active'))

    categories = Product.objects.values_list('category', flat=True).distinct()

    context = {
        'products': queryset,
        'categories': categories,
        'search_query': search_query,
        'category_filter': category_filter,
        'status_filter': status_filter,
    }
    return render(request, 'products/product_list.html', context)


@login_required
@admin_required
def product_create(request):
    if request.method == 'POST':
        code = request.POST.get('product_code', '').strip()
        name = request.POST.get('name', '').strip()
        category = request.POST.get('category', '').strip()
        price_str = request.POST.get('price', '').strip()
        stock_str = request.POST.get('stock_quantity', '0').strip()
        is_active = request.POST.get('is_active') == 'on'

        errors = []
        if not code or not name or not category:
            errors.append("Product code, name, and category are mandatory.")

        if Product.objects.filter(product_code=code).exists():
            errors.append(f"Product code '{code}' is already taken.")

        try:
            price = Decimal(price_str)
            if price < Decimal('0.00'):
                errors.append("Price cannot be negative.")
        except Exception:
            errors.append("Price must be a valid positive number.")

        try:
            stock = int(stock_str)
            if stock < 0:
                errors.append("Stock quantity cannot be negative.")
        except Exception:
            errors.append("Stock quantity must be a whole positive integer.")

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            product = Product.objects.create(
                product_code=code,
                name=name,
                category=category,
                price=price,
                stock_quantity=stock,
                is_active=is_active
            )
            if stock > 0:
                StockMovement.objects.create(
                    product=product,
                    movement_type=StockMovement.TYPE_OPENING,
                    quantity_change=stock,
                    related_order=None,
                    reason="Initial opening stock on creation",
                    created_by=request.user
                )
            messages.success(request, f"Product '{product.name}' created successfully.")
            return redirect('product_list')

    return render(request, 'products/product_form.html', {'action': 'Create'})


@login_required
@admin_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category = request.POST.get('category', '').strip()
        price_str = request.POST.get('price', '').strip()
        is_active = request.POST.get('is_active') == 'on'

        errors = []
        if not name or not category:
            errors.append("Product name and category are required.")

        try:
            price = Decimal(price_str)
            if price < Decimal('0.00'):
                errors.append("Price cannot be negative.")
        except Exception:
            errors.append("Price must be a valid decimal number.")

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            product.name = name
            product.category = category
            product.price = price
            product.is_active = is_active
            product.save()
            messages.success(request, f"Product '{product.name}' updated successfully.")
            return redirect('product_list')

    return render(request, 'products/product_form.html', {'product': product, 'action': 'Edit'})


@login_required
@admin_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if not product.can_delete():
        messages.error(
            request,
            f"Cannot delete product '{product.product_code}' because it is referenced in orders or stock movements. You can deactivate it instead."
        )
        return redirect('product_list')

    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f"Product '{name}' deleted successfully.")
        return redirect('product_list')

    return render(request, 'products/product_confirm_delete.html', {'product': product})


@login_required
@admin_required
def product_toggle_status(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.is_active = not product.is_active
    product.save(update_fields=['is_active'])
    status_str = "activated" if product.is_active else "deactivated"
    messages.success(request, f"Product '{product.product_code}' {status_str} successfully.")
    return redirect('product_list')


@login_required
@admin_required
def stock_adjust_view(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        qty_change_str = request.POST.get('quantity_change', '').strip()
        reason = request.POST.get('reason', '').strip()

        try:
            qty_change = int(qty_change_str)
            StockService.adjust_stock(product.id, qty_change, reason, request.user)
            messages.success(request, f"Stock for '{product.name}' adjusted by {qty_change:+d} units.")
            return redirect('product_list')
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
        except Exception as e:
            messages.error(request, f"Adjustment failed: {str(e)}")

    movements = product.stock_movements.select_related('created_by')[:10]
    return render(request, 'products/stock_adjust.html', {'product': product, 'movements': movements})


# ==========================================
# Sales Order Management Views
# ==========================================

@login_required
def order_list(request):
    user = request.user
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('q', '').strip()

    # Sales Users can only view their own orders; Admins view all
    queryset = SalesOrder.objects.all() if user.is_admin_user else SalesOrder.objects.filter(created_by=user)

    if status_filter in ('draft', 'confirmed', 'cancelled'):
        queryset = queryset.filter(status=status_filter)

    if search_query:
        queryset = queryset.filter(
            Q(order_number__icontains=search_query) |
            Q(customer__name__icontains=search_query)
        )

    queryset = queryset.select_related('customer', 'created_by')

    context = {
        'orders': queryset,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    return render(request, 'orders/order_list.html', context)


@login_required
def order_create_view(request):
    active_customers = Customer.objects.filter(is_active=True)
    active_products = Product.objects.filter(is_active=True)

    if request.method == 'POST':
        customer_id = request.POST.get('customer_id')
        discount_percentage = request.POST.get('discount_percentage', '0.00')

        product_ids = request.POST.getlist('product_id[]')
        quantities = request.POST.getlist('quantity[]')

        try:
            customer = get_object_or_404(Customer, id=customer_id)
            items_data = []
            for p_id, qty in zip(product_ids, quantities):
                if p_id and qty:
                    items_data.append({
                        'product_id': int(p_id),
                        'quantity': int(qty)
                    })

            order = OrderService.create_order(
                user=request.user,
                customer=customer,
                items_data=items_data,
                discount_percentage=discount_percentage
            )
            messages.success(request, f"Sales Order {order.order_number} created successfully as Draft.")
            return redirect('order_detail', pk=order.id)
        except (ValidationError, InsufficientStockError) as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
        except Exception as e:
            messages.error(request, f"Order creation failed: {str(e)}")

    context = {
        'customers': active_customers,
        'products': active_products,
    }
    return render(request, 'orders/order_create.html', context)


@login_required
def order_detail_view(request, pk):
    order = get_object_or_404(
        SalesOrder.objects.select_related('customer', 'created_by').prefetch_related('items__product'),
        pk=pk
    )

    # Permission check: Sales User cannot access another user's order
    if not request.user.is_admin_user and order.created_by != request.user:
        return HttpResponseForbidden("Access denied. You do not have permission to view another user's order.")

    context = {
        'order': order,
        'items': order.items.all(),
    }
    return render(request, 'orders/order_detail.html', context)


@login_required
def order_confirm_view(request, pk):
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('order_detail', pk=pk)

    order = get_object_or_404(SalesOrder, pk=pk)

    if not request.user.is_admin_user and order.created_by != request.user:
        return HttpResponseForbidden("Access denied. You cannot confirm an order belonging to another user.")

    try:
        OrderService.confirm_order(order.id, request.user)
        messages.success(request, f"Order {order.order_number} has been confirmed. Stock deducted.")
    except InsufficientStockError as e:
        messages.error(request, str(e))
    except (ValidationError, PermissionDenied) as e:
        messages.error(request, str(e.message if hasattr(e, 'message') else e))
    except Exception as e:
        messages.error(request, f"Confirmation failed: {str(e)}")

    return redirect('order_detail', pk=pk)


@login_required
def order_cancel_view(request, pk):
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('order_detail', pk=pk)

    order = get_object_or_404(SalesOrder, pk=pk)

    if not request.user.is_admin_user and order.created_by != request.user:
        return HttpResponseForbidden("Access denied. You cannot cancel an order belonging to another user.")

    try:
        OrderService.cancel_order(order.id, request.user)
        messages.success(request, f"Order {order.order_number} has been cancelled.")
    except (ValidationError, PermissionDenied) as e:
        messages.error(request, str(e.message if hasattr(e, 'message') else e))
    except Exception as e:
        messages.error(request, f"Cancellation failed: {str(e)}")

    return redirect('order_detail', pk=pk)


# ==========================================
# Reports & SQL Views (Part 9)
# ==========================================

@login_required
def customer_sales_report(request):
    """
    Customer Sales Summary:
    Customer, confirmed order count, total sales after discount.
    Supports order-date range.
    Includes customers with no Confirmed orders in that range (showing 0 totals).
    Avoids counting one order multiple times because it has multiple item rows.
    """
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    filter_kwargs = {'orders__status': SalesOrder.STATUS_CONFIRMED}
    if start_date:
        filter_kwargs['orders__order_date__gte'] = start_date
    if end_date:
        filter_kwargs['orders__order_date__lte'] = end_date

    # Use distinct count on order id and aggregate sum of grand_total
    customers_summary = Customer.objects.annotate(
        confirmed_order_count=Count('orders__id', filter=Q(**filter_kwargs), distinct=True),
        total_sales=Coalesce(
            Sum('orders__grand_total', filter=Q(**filter_kwargs), distinct=True),
            Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    ).order_by('-total_sales', 'name')

    context = {
        'customers_summary': customers_summary,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'reports/customer_sales.html', context)


@login_required
def product_sales_report(request):
    """
    Product Sales Summary:
    Product, quantity sold in confirmed orders, gross item value before order discount.
    """
    product_summary = Product.objects.annotate(
        quantity_sold=Coalesce(
            Sum('order_items__quantity', filter=Q(order_items__sales_order__status=SalesOrder.STATUS_CONFIRMED)),
            0
        ),
        gross_value=Coalesce(
            Sum('order_items__amount', filter=Q(order_items__sales_order__status=SalesOrder.STATUS_CONFIRMED)),
            Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    ).order_by('-quantity_sold', 'product_code')

    return render(request, 'reports/product_sales.html', {'product_summary': product_summary})


@login_required
def low_stock_report(request):
    """
    Low Stock Report:
    Products with stock below a user-entered threshold (default 10).
    """
    threshold_str = request.GET.get('threshold', '10')
    try:
        threshold = int(threshold_str)
        if threshold < 0:
            threshold = 10
    except ValueError:
        threshold = 10

    low_stock_products = Product.objects.filter(
        stock_quantity__lt=threshold,
        is_active=True
    ).order_by('stock_quantity')

    return render(request, 'reports/low_stock.html', {
        'products': low_stock_products,
        'threshold': threshold
    })


@login_required
def stock_movement_report(request):
    """
    Stock Movement History:
    Product, movement type, quantity change, order, reason, timestamp.
    """
    movements = StockMovement.objects.select_related(
        'product', 'related_order', 'created_by'
    ).order_by('-timestamp')[:100]

    return render(request, 'reports/stock_movements.html', {'movements': movements})


# ==========================================
# CSV Import View (Part 10)
# ==========================================

@login_required
@admin_required
def csv_import_view(request):
    """
    Admin-only product import with all-or-nothing validation.
    """
    import_results = None

    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "Uploaded file must be a .csv file.")
        else:
            try:
                content = csv_file.read()
                success, count, errors = CSVImportService.import_products_csv(content, request.user)
                if success:
                    messages.success(request, f"Successfully imported {count} products and recorded opening stock movements.")
                    return redirect('product_list')
                else:
                    import_results = {'errors': errors}
                    messages.error(request, f"Import rejected: {len(errors)} error(s) found. No products were imported.")
            except Exception as e:
                messages.error(request, f"Import failed with unexpected error: {str(e)}")

    return render(request, 'csv_import/import_products.html', {'results': import_results})
