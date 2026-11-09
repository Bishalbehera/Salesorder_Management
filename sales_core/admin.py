from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Customer, Product, SalesOrder, SalesOrderItem, StockMovement


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'name', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('name',)}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'role', 'password', 'is_staff', 'is_superuser'),
        }),
    )
    search_fields = ('email', 'name')
    ordering = ('email',)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'mobile', 'city', 'is_active', 'created_at')
    list_filter = ('is_active', 'city')
    search_fields = ('name', 'email', 'mobile')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_code', 'name', 'category', 'price', 'stock_quantity', 'is_active')
    list_filter = ('is_active', 'category')
    search_fields = ('product_code', 'name')


class SalesOrderItemInline(admin.TabularInline):
    model = SalesOrderItem
    extra = 0
    readonly_fields = ('amount',)


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'customer', 'order_date', 'status', 'grand_total', 'created_by')
    list_filter = ('status', 'order_date')
    search_fields = ('order_number', 'customer__name')
    inlines = [SalesOrderItemInline]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('product', 'movement_type', 'quantity_change', 'related_order', 'created_by', 'timestamp')
    list_filter = ('movement_type', 'timestamp')
    search_fields = ('product__product_code', 'product__name', 'reason')
