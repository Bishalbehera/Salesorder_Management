from rest_framework import serializers
from decimal import Decimal
from .models import Product, Customer, SalesOrder, SalesOrderItem, StockMovement, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'role']


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'product_code', 'name', 'category', 'price', 'stock_quantity', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name', 'email', 'mobile', 'city', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class SalesOrderItemSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.product_code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = SalesOrderItem
        fields = ['id', 'product', 'product_code', 'product_name', 'quantity', 'rate', 'amount']
        read_only_fields = ['id', 'amount', 'rate', 'product_code', 'product_name']


class OrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(required=True)
    quantity = serializers.IntegerField(required=True, min_value=1)


class OrderCreateSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField(required=True)
    discount_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        default=Decimal('0.00'),
        min_value=Decimal('0.00'),
        max_value=Decimal('20.00')
    )
    items = OrderItemInputSerializer(many=True, required=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Order must have at least one product item.")
        product_ids = [item['product_id'] for item in value]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError("Duplicate products within the same order are not allowed.")
        return value


class SalesOrderDetailSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    items = SalesOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = SalesOrder
        fields = [
            'id', 'order_number', 'customer', 'order_date', 'status',
            'discount_percentage', 'subtotal', 'discount_amount',
            'grand_total', 'created_by', 'created_at', 'updated_at', 'items'
        ]
        read_only_fields = fields


class StockMovementSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.product_code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    order_number = serializers.CharField(source='related_order.order_number', read_only=True, default=None)

    class Meta:
        model = StockMovement
        fields = [
            'id', 'product', 'product_code', 'product_name', 'movement_type',
            'quantity_change', 'order_number', 'reason', 'created_by_name', 'timestamp'
        ]
        read_only_fields = fields
