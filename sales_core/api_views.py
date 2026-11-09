"""
REST API Views for Sales Order & Inventory Management.
Complies with Part 8 of the technical assignment.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.models import Q
from decimal import Decimal

from .models import Product, Customer, SalesOrder
from .serializers import (
    ProductSerializer,
    SalesOrderDetailSerializer,
    OrderCreateSerializer
)
from .services import OrderService, InsufficientStockError


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class ProductListAPIView(APIView):
    """
    GET /api/products
    List active products with optional search query and pagination.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('search', '').strip()
        queryset = Product.objects.filter(is_active=True)

        if query:
            queryset = queryset.filter(
                Q(product_code__icontains=query) |
                Q(name__icontains=query) |
                Q(category__icontains=query)
            )

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = ProductSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ProductDetailAPIView(APIView):
    """
    GET /api/products/<int:pk>/
    Retrieve individual product price & available stock for frontend dynamic updates.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, is_active=True)
        serializer = ProductSerializer(product)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrderListCreateAPIView(APIView):
    """
    POST /api/orders
    Create a new Draft order with backend-calculated totals.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "Validation failed", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data
        customer = get_object_or_404(Customer, id=data['customer_id'])

        try:
            order = OrderService.create_order(
                user=request.user,
                customer=customer,
                items_data=data['items'],
                discount_percentage=data.get('discount_percentage', Decimal('0.00'))
            )
            response_serializer = SalesOrderDetailSerializer(order)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            msg = e.message if hasattr(e, 'message') else str(e)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Failed to create order: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


class OrderDetailAPIView(APIView):
    """
    GET /api/orders/{id}
    Retrieve an accessible order and its items.
    Enforces role-based permissions: Sales Users can only view their own orders.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            order = SalesOrder.objects.prefetch_related('items__product', 'customer', 'created_by').get(pk=pk)
        except SalesOrder.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        # Enforce role-based permission
        if not request.user.is_admin_user and order.created_by != request.user:
            return Response(
                {"error": "Access denied. You do not have permission to view another user's order."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = SalesOrderDetailSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrderConfirmAPIView(APIView):
    """
    POST /api/orders/{id}/confirm
    Confirm an order and deduct stock atomically.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            order = SalesOrder.objects.get(pk=pk)
        except SalesOrder.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        if not request.user.is_admin_user and order.created_by != request.user:
            return Response(
                {"error": "Access denied. You cannot confirm an order belonging to another user."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            confirmed_order = OrderService.confirm_order(order.id, request.user)
            serializer = SalesOrderDetailSerializer(confirmed_order)
            return Response(
                {"message": "Order successfully confirmed and stock deducted.", "order": serializer.data},
                status=status.HTTP_200_OK
            )
        except InsufficientStockError as e:
            return Response(
                {"error": str(e), "insufficient_items": e.details},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (ValidationError, PermissionDenied) as e:
            msg = e.message if hasattr(e, 'message') else str(e)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"An error occurred while confirming order: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


class OrderCancelAPIView(APIView):
    """
    POST /api/orders/{id}/cancel
    Cancel an order and restore stock if previously confirmed.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            order = SalesOrder.objects.get(pk=pk)
        except SalesOrder.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        if not request.user.is_admin_user and order.created_by != request.user:
            return Response(
                {"error": "Access denied. You cannot cancel an order belonging to another user."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            cancelled_order = OrderService.cancel_order(order.id, request.user)
            serializer = SalesOrderDetailSerializer(cancelled_order)
            return Response(
                {"message": "Order successfully cancelled.", "order": serializer.data},
                status=status.HTTP_200_OK
            )
        except (ValidationError, PermissionDenied) as e:
            msg = e.message if hasattr(e, 'message') else str(e)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"An error occurred while cancelling order: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
