from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.providers.models import CourierProviderProfile, RestaurantProviderProfile


class FoodOrderStatus(models.TextChoices):
    PLACED = 'placed', 'Order Placed'
    CONFIRMED = 'confirmed', 'Confirmed'
    IN_PREP = 'in_prep', 'In Prep'
    KITCHEN_SEALED = 'kitchen_sealed', 'Kitchen Sealed'
    COURIER_ASSIGNED = 'courier_assigned', 'Courier Assigned'
    IN_TRANSIT = 'in_transit', 'In Transit'
    HANDED_OVER = 'handed_over', 'Handed Over'
    CANCELLED = 'cancelled', 'Cancelled'


class FoodPaymentMethod(models.TextChoices):
    CARD = 'card', 'Card'
    CASH_ON_DELIVERY = 'cash_on_delivery', 'Cash on Delivery'


class FoodPaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PAID = 'paid', 'Paid'
    FAILED = 'failed', 'Failed'
    CASH_DUE = 'cash_due', 'Cash Due'
    REFUNDED = 'refunded', 'Refunded'


class FoodCancellationActor(models.TextChoices):
    CUSTOMER = 'customer', 'Customer'
    RESTAURANT = 'restaurant', 'Restaurant'
    COURIER = 'courier', 'Courier'
    SYSTEM = 'system', 'System'
    SUPER_ADMIN = 'super_admin', 'Super Admin'


class MenuCategory(models.Model):
    restaurant = models.ForeignKey(RestaurantProviderProfile, on_delete=models.CASCADE, related_name='menu_categories')
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default='')
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'name']
        constraints = [
            models.UniqueConstraint(fields=['restaurant', 'name'], name='unique_menu_category_per_restaurant'),
        ]
        indexes = [
            models.Index(fields=['restaurant', 'is_active', 'display_order']),
        ]

    def __str__(self):
        return f'{self.restaurant_id} - {self.name}'


class FoodItem(models.Model):
    restaurant = models.ForeignKey(RestaurantProviderProfile, on_delete=models.CASCADE, related_name='food_items')
    category = models.ForeignKey(MenuCategory, on_delete=models.PROTECT, related_name='food_items')
    photo = models.ImageField(upload_to='food/items/', blank=True, default='')
    name = models.CharField(max_length=160)
    culinary_description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='BSD')
    estimated_prep_window = models.CharField(max_length=80)
    dietary_tags = models.JSONField(blank=True, default=list)
    available_today = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category__display_order', 'name']
        indexes = [
            models.Index(fields=['restaurant', 'available_today', 'is_active']),
            models.Index(fields=['category', 'is_active']),
        ]

    def __str__(self):
        return self.name


class FoodOrder(models.Model):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='food_orders')
    restaurant = models.ForeignKey(RestaurantProviderProfile, on_delete=models.PROTECT, related_name='food_orders')
    courier = models.ForeignKey(
        CourierProviderProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='food_deliveries',
    )
    status = models.CharField(max_length=32, choices=FoodOrderStatus.choices, default=FoodOrderStatus.PLACED)

    delivery_address = models.CharField(max_length=255)
    delivery_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    delivery_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    delivery_place_id = models.CharField(max_length=255, blank=True, default='')
    delivery_note = models.CharField(max_length=255, blank=True, default='')

    currency = models.CharField(max_length=3, default='BSD')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    service_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tip_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    payment_method = models.CharField(max_length=32, choices=FoodPaymentMethod.choices, default=FoodPaymentMethod.CASH_ON_DELIVERY)
    payment_method_reference = models.CharField(max_length=255, blank=True, default='')
    payment_status = models.CharField(max_length=32, choices=FoodPaymentStatus.choices, default=FoodPaymentStatus.CASH_DUE)

    estimated_handover_min_minutes = models.PositiveIntegerField(null=True, blank=True)
    estimated_handover_max_minutes = models.PositiveIntegerField(null=True, blank=True)
    estimated_handover_at = models.DateTimeField(null=True, blank=True)

    courier_current_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    courier_current_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    courier_location_updated_at = models.DateTimeField(null=True, blank=True)

    placed_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    in_prep_at = models.DateTimeField(null=True, blank=True)
    kitchen_sealed_at = models.DateTimeField(null=True, blank=True)
    courier_assigned_at = models.DateTimeField(null=True, blank=True)
    in_transit_at = models.DateTimeField(null=True, blank=True)
    handed_over_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.CharField(max_length=32, choices=FoodCancellationActor.choices, blank=True, default='')
    cancellation_reason = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['customer', '-created_at']),
            models.Index(fields=['restaurant', '-created_at']),
            models.Index(fields=['courier', '-created_at']),
        ]

    def __str__(self):
        return f'Food order #{self.pk} - {self.status}'

    @property
    def is_terminal(self):
        return self.status in {FoodOrderStatus.HANDED_OVER, FoodOrderStatus.CANCELLED}

    @property
    def can_customer_cancel(self):
        return self.status in {FoodOrderStatus.PLACED, FoodOrderStatus.CONFIRMED}

    def mark_courier_location(self, latitude, longitude):
        self.courier_current_latitude = latitude
        self.courier_current_longitude = longitude
        self.courier_location_updated_at = timezone.now()
        self.save(update_fields=['courier_current_latitude', 'courier_current_longitude', 'courier_location_updated_at', 'updated_at'])


class FoodOrderItem(models.Model):
    order = models.ForeignKey(FoodOrder, on_delete=models.CASCADE, related_name='items')
    food_item = models.ForeignKey(FoodItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items')
    item_name = models.CharField(max_length=160)
    category_name = models.CharField(max_length=120, blank=True, default='')
    quantity = models.PositiveSmallIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='BSD')
    notes = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        indexes = [models.Index(fields=['order'])]

    def __str__(self):
        return f'{self.quantity} x {self.item_name}'


class FoodItemReview(models.Model):
    order_item = models.OneToOneField(FoodOrderItem, on_delete=models.CASCADE, related_name='review')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='food_item_reviews')
    restaurant = models.ForeignKey(RestaurantProviderProfile, on_delete=models.CASCADE, related_name='food_item_reviews')
    food_item = models.ForeignKey(FoodItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviews')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    notes = models.TextField(blank=True, default='')
    impressed = models.JSONField(blank=True, default=list)
    tip_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['restaurant', '-created_at']),
            models.Index(fields=['food_item', '-created_at']),
        ]

    def __str__(self):
        return f'Food item review #{self.pk} - {self.rating}/5'
