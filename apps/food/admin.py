from django.contrib import admin

from .models import FoodItem, FoodItemReview, FoodOrder, FoodOrderItem, MenuCategory


@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'restaurant', 'name', 'display_order', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'restaurant__restaurant_name', 'restaurant__user__email')


@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'restaurant', 'category', 'name', 'price', 'currency', 'available_today', 'is_active')
    list_filter = ('available_today', 'is_active', 'currency', 'created_at')
    search_fields = ('name', 'culinary_description', 'restaurant__restaurant_name')


class FoodOrderItemInline(admin.TabularInline):
    model = FoodOrderItem
    extra = 0
    readonly_fields = ('item_name', 'category_name', 'quantity', 'unit_price', 'line_total', 'currency')


@admin.register(FoodOrder)
class FoodOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'restaurant', 'courier', 'status', 'payment_method', 'payment_status', 'total_amount', 'created_at')
    list_filter = ('status', 'payment_method', 'payment_status', 'created_at')
    search_fields = ('customer__email', 'restaurant__restaurant_name', 'delivery_address')
    inlines = [FoodOrderItemInline]


@admin.register(FoodItemReview)
class FoodItemReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'order_item', 'customer', 'restaurant', 'rating', 'tip_amount', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('customer__email', 'restaurant__restaurant_name', 'order_item__item_name')
