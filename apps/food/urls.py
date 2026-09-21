from django.urls import path

from .views import (
    CourierFoodOrderLocationView,
    CustomerFoodItemReviewView,
    CustomerFoodOrderCancelView,
    CustomerFoodOrderDetailView,
    CustomerFoodOrderListCreateView,
    ProviderCategoryDetailView,
    ProviderCategoryListCreateView,
    ProviderFoodItemDetailView,
    ProviderFoodItemListCreateView,
    ProviderFoodOrderDetailView,
    ProviderFoodOrderListView,
    ProviderFoodOrderStatusView,
    RestaurantDetailView,
    RestaurantListView,
    RestaurantMenuView,
    SuperAdminFoodOrderDetailView,
    SuperAdminFoodOrderListView,
    SuperAdminFoodOrderPaymentStatusView,
)

app_name = 'food'

urlpatterns = [
    path('restaurants/', RestaurantListView.as_view(), name='restaurants'),
    path('restaurants/<int:pk>/', RestaurantDetailView.as_view(), name='restaurant-detail'),
    path('restaurants/<int:pk>/menu/', RestaurantMenuView.as_view(), name='restaurant-menu'),

    path('my-orders/', CustomerFoodOrderListCreateView.as_view(), name='customer-orders'),
    path('my-orders/<int:pk>/', CustomerFoodOrderDetailView.as_view(), name='customer-order-detail'),
    path('my-orders/<int:pk>/cancel/', CustomerFoodOrderCancelView.as_view(), name='customer-order-cancel'),
    path('my-order-items/<int:item_pk>/review/', CustomerFoodItemReviewView.as_view(), name='customer-order-item-review'),

    path('provider/categories/', ProviderCategoryListCreateView.as_view(), name='provider-categories'),
    path('provider/categories/<int:pk>/', ProviderCategoryDetailView.as_view(), name='provider-category-detail'),
    path('provider/items/', ProviderFoodItemListCreateView.as_view(), name='provider-food-items'),
    path('provider/items/<int:pk>/', ProviderFoodItemDetailView.as_view(), name='provider-food-item-detail'),
    path('provider/orders/', ProviderFoodOrderListView.as_view(), name='provider-food-orders'),
    path('provider/orders/<int:pk>/', ProviderFoodOrderDetailView.as_view(), name='provider-food-order-detail'),
    path('provider/orders/<int:pk>/status/', ProviderFoodOrderStatusView.as_view(), name='provider-food-order-status'),

    path('courier/orders/<int:pk>/location/', CourierFoodOrderLocationView.as_view(), name='courier-food-order-location'),

    path('admin/orders/', SuperAdminFoodOrderListView.as_view(), name='admin-food-orders'),
    path('admin/orders/<int:pk>/', SuperAdminFoodOrderDetailView.as_view(), name='admin-food-order-detail'),
    path('admin/orders/<int:pk>/payment-status/', SuperAdminFoodOrderPaymentStatusView.as_view(), name='admin-food-order-payment-status'),
]
