from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
import uuid


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        extra_fields.setdefault('username', email)
        extra_fields.setdefault('role', User.ROLE_SALES)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.ROLE_ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    ROLE_ADMIN = 'admin'
    ROLE_SALES = 'sales'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_SALES, 'Sales User'),
    ]

    name = models.CharField(max_length=150, help_text="User's full name")
    email = models.EmailField(unique=True, db_index=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_SALES, db_index=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"

    @property
    def is_admin_user(self):
        return self.role == self.ROLE_ADMIN or self.is_superuser

    @property
    def is_sales_user(self):
        return self.role == self.ROLE_SALES


class Customer(models.Model):
    name = models.CharField(max_length=150, db_index=True)
    email = models.EmailField(db_index=True)
    mobile = models.CharField(max_length=20, db_index=True)
    city = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name', 'email', 'mobile']),
        ]

    def __str__(self):
        return f"{self.name} ({self.city})"

    def can_delete(self):
        return not self.orders.exists()

    def delete(self, *args, **kwargs):
        if self.orders.exists():
            raise ProtectedError(
                "Cannot delete customer because existing sales orders reference it. Please deactivate the customer instead.",
                self.orders.all()
            )
        return super().delete(*args, **kwargs)


class Product(models.Model):
    product_code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=150, db_index=True)
    category = models.CharField(max_length=100, db_index=True)
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Price cannot be negative"
    )
    stock_quantity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Stock quantity cannot be negative"
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['product_code']
        indexes = [
            models.Index(fields=['product_code', 'name']),
            models.Index(fields=['category', 'is_active']),
        ]

    def __str__(self):
        return f"{self.product_code} - {self.name}"

    def can_delete(self):
        return not (self.order_items.exists() or self.stock_movements.exists())

    def delete(self, *args, **kwargs):
        if self.order_items.exists() or self.stock_movements.exists():
            raise ProtectedError(
                "Cannot delete product because it is referenced in sales orders or stock movements. Please deactivate the product instead.",
                self
            )
        return super().delete(*args, **kwargs)


class SalesOrder(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    order_number = models.CharField(max_length=50, unique=True, db_index=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='orders')
    order_date = models.DateField(default=timezone.now, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('20.00'))
        ],
        help_text="Discount percentage allowed strictly between 0 and 20"
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='orders')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-id']
        indexes = [
            models.Index(fields=['order_date', 'status']),
            models.Index(fields=['customer', 'status']),
        ]

    def __str__(self):
        return f"{self.order_number} ({self.get_status_display()})"

    @classmethod
    def generate_unique_order_number(cls):
        date_str = timezone.now().strftime('%Y%m%d')
        # Generate sequence number for today
        count_today = cls.objects.filter(order_number__startswith=f"SO-{date_str}-").count()
        candidate = f"SO-{date_str}-{count_today + 1:04d}"
        while cls.objects.filter(order_number=candidate).exists():
            count_today += 1
            candidate = f"SO-{date_str}-{count_today + 1:04d}"
        return candidate

    def recalculate_totals(self, save=True):
        """
        Backend calculation rules:
        Item Amount = Quantity * Rate
        Subtotal = Sum of Item Amounts
        Discount Amount = Subtotal * Discount Percentage / 100
        Grand Total = Subtotal - Discount Amount
        Round monetary amounts to 2 decimal places using standard ROUND_HALF_UP.
        """
        items = self.items.all()
        subtotal = Decimal('0.00')
        for item in items:
            item_amt = (Decimal(str(item.quantity)) * Decimal(str(item.rate))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if item.amount != item_amt:
                item.amount = item_amt
                item.save(update_fields=['amount'])
            subtotal += item_amt

        subtotal = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        disc_pct = Decimal(str(self.discount_percentage or '0.00'))
        disc_amt = (subtotal * disc_pct / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        grand = (subtotal - disc_amt).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        self.subtotal = subtotal
        self.discount_amount = disc_amt
        self.grand_total = grand
        if save:
            self.save(update_fields=['subtotal', 'discount_amount', 'grand_total', 'updated_at'])


class SalesOrderItem(models.Model):
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='order_items')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Stored price rate at time of order creation"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['sales_order', 'product'], name='unique_product_per_order')
        ]

    def __str__(self):
        return f"{self.product.name} x {self.quantity} @ {self.rate}"

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError({'quantity': "Quantity must be a positive whole number greater than 0."})
        if self.rate < Decimal('0.00'):
            raise ValidationError({'rate': "Rate cannot be negative."})

    def save(self, *args, **kwargs):
        self.clean()
        self.amount = (Decimal(str(self.quantity)) * Decimal(str(self.rate))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        super().save(*args, **kwargs)


class StockMovement(models.Model):
    TYPE_OPENING = 'OPENING_STOCK'
    TYPE_ADJUSTMENT = 'ADJUSTMENT'
    TYPE_ORDER_CONFIRM = 'ORDER_CONFIRM'
    TYPE_ORDER_CANCEL = 'ORDER_CANCEL'
    MOVEMENT_TYPE_CHOICES = [
        (TYPE_OPENING, 'Opening Stock / Import'),
        (TYPE_ADJUSTMENT, 'Manual Adjustment'),
        (TYPE_ORDER_CONFIRM, 'Order Confirmed (Deduction)'),
        (TYPE_ORDER_CANCEL, 'Order Cancelled (Restoration)'),
    ]

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='stock_movements')
    movement_type = models.CharField(max_length=30, choices=MOVEMENT_TYPE_CHOICES, db_index=True)
    quantity_change = models.IntegerField(help_text="Positive for addition, negative for deduction")
    related_order = models.ForeignKey(
        SalesOrder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='stock_movements'
    )
    reason = models.TextField(help_text="Mandatory reason for manual adjustments or automated description")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='stock_movements')
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['product', 'timestamp']),
            models.Index(fields=['movement_type', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.product.product_code} | {self.movement_type} | {self.quantity_change:+d} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
