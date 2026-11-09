from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.dashboard_view, name='dashboard'),

    # Customers
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/add/', views.customer_create, name='customer_create'),
    path('customers/<int:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('customers/<int:pk>/delete/', views.customer_delete, name='customer_delete'),
    path('customers/<int:pk>/toggle/', views.customer_toggle_status, name='customer_toggle_status'),

    # Products
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_create, name='product_create'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('products/<int:pk>/toggle/', views.product_toggle_status, name='product_toggle_status'),
    path('products/<int:pk>/adjust/', views.stock_adjust_view, name='stock_adjust'),

    # Orders
    path('orders/', views.order_list, name='order_list'),
    path('orders/create/', views.order_create_view, name='order_create'),
    path('orders/<int:pk>/', views.order_detail_view, name='order_detail'),
    path('orders/<int:pk>/confirm/', views.order_confirm_view, name='order_confirm'),
    path('orders/<int:pk>/cancel/', views.order_cancel_view, name='order_cancel'),

    # Reports
    path('reports/customers/', views.customer_sales_report, name='report_customer_sales'),
    path('reports/products/', views.product_sales_report, name='report_product_sales'),
    path('reports/low-stock/', views.low_stock_report, name='report_low_stock'),
    path('reports/stock-movements/', views.stock_movement_report, name='report_stock_movements'),

    # CSV Import
    path('import/products/', views.csv_import_view, name='csv_import'),

    # REST APIs (Part 8)
    path('api/products/', api_views.ProductListAPIView.as_view(), name='api_products_list'),
    path('api/products/<int:pk>/', api_views.ProductDetailAPIView.as_view(), name='api_product_detail'),
    path('api/orders/', api_views.OrderListCreateAPIView.as_view(), name='api_orders_create'),
    path('api/orders/<int:pk>/', api_views.OrderDetailAPIView.as_view(), name='api_order_detail'),
    path('api/orders/<int:pk>/confirm/', api_views.OrderConfirmAPIView.as_view(), name='api_order_confirm'),
    path('api/orders/<int:pk>/cancel/', api_views.OrderCancelAPIView.as_view(), name='api_order_cancel'),
]
