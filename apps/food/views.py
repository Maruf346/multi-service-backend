from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from apps.providers.models import ProviderOnboardingStatus, RestaurantProviderProfile
from apps.users.permissions import IsCustomer, IsServiceProvider, IsSuperAdmin
from .models import FoodCancellationActor, FoodItem, FoodOrder, FoodOrderItem, FoodOrderStatus, MenuCategory
from .serializers import (
    FoodCourierLocationSerializer,
    FoodDetailSerializer,
    FoodItemListResponseSerializer,
    FoodItemReviewCreateSerializer,
    FoodItemReviewResponseSerializer,
    FoodItemReviewSerializer,
    FoodItemSerializer,
    FoodItemWriteSerializer,
    FoodOrderActionResponseSerializer,
    FoodOrderCancelSerializer,
    FoodOrderCreateSerializer,
    FoodOrderListResponseSerializer,
    FoodOrderSerializer,
    FoodOrderStatusUpdateSerializer,
    FoodPaymentStatusUpdateSerializer,
    MenuCategoryListResponseSerializer,
    MenuCategorySerializer,
    RestaurantListResponseSerializer,
    RestaurantMenuSerializer,
    RestaurantPublicSerializer,
)
from .services import FoodService


def validation_detail(exc):
    if hasattr(exc, 'message_dict'):
        return exc.message_dict
    if hasattr(exc, 'messages'):
        return exc.messages
    return str(exc)


def get_restaurant_provider_profile(user):
    try:
        return user.restaurant_provider_profile
    except Exception:
        return None


def get_courier_provider_profile(user):
    try:
        return user.courier_provider_profile
    except Exception:
        return None


class PaginatedFoodListMixin:
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    serializer_class = None

    def paginated_response(self, request, queryset, serializer_class=None):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = (serializer_class or self.serializer_class)(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class RestaurantListView(PaginatedFoodListMixin, APIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = RestaurantPublicSerializer

    @extend_schema(
        tags=['Food - Customers'],
        operation_id='customer_list_available_restaurants',
        summary='List restaurants accepting food orders',
        parameters=[
            OpenApiParameter('cuisine_concept', str, required=False),
            OpenApiParameter('island_service_hub', str, required=False),
            OpenApiParameter('page', int, required=False),
            OpenApiParameter('page_size', int, required=False),
        ],
        responses={200: RestaurantListResponseSerializer},
    )
    def get(self, request):
        queryset = RestaurantProviderProfile.objects.filter(
            onboarding_status=ProviderOnboardingStatus.COMPLETED,
            is_active=True,
            accepting_orders=True,
        ).order_by('restaurant_name')
        cuisine = (request.query_params.get('cuisine_concept') or '').strip()
        hub = (request.query_params.get('island_service_hub') or '').strip()
        if cuisine:
            queryset = queryset.filter(cuisine_concept__iexact=cuisine)
        if hub:
            queryset = queryset.filter(island_service_hub__iexact=hub)
        return self.paginated_response(request, queryset)


class RestaurantDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(
        tags=['Food - Customers'],
        operation_id='customer_retrieve_restaurant',
        summary='Retrieve an available restaurant',
        responses={200: RestaurantPublicSerializer, 404: FoodDetailSerializer},
    )
    def get(self, request, pk):
        restaurant = get_object_or_404(
            RestaurantProviderProfile,
            pk=pk,
            onboarding_status=ProviderOnboardingStatus.COMPLETED,
            is_active=True,
            accepting_orders=True,
        )
        return Response(RestaurantPublicSerializer(restaurant, context={'request': request}).data)


class RestaurantMenuView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(
        tags=['Food - Customers'],
        operation_id='customer_retrieve_restaurant_menu',
        summary='Retrieve restaurant categories and available food items',
        responses={200: RestaurantMenuSerializer, 404: FoodDetailSerializer},
    )
    def get(self, request, pk):
        restaurant = get_object_or_404(
            RestaurantProviderProfile,
            pk=pk,
            onboarding_status=ProviderOnboardingStatus.COMPLETED,
            is_active=True,
            accepting_orders=True,
        )
        categories = MenuCategory.objects.filter(restaurant=restaurant, is_active=True).order_by('display_order', 'name')
        food_items = FoodItem.objects.select_related('category').filter(
            restaurant=restaurant,
            is_active=True,
            available_today=True,
            category__is_active=True,
        )
        return Response({
            'restaurant': RestaurantPublicSerializer(restaurant, context={'request': request}).data,
            'categories': MenuCategorySerializer(categories, many=True).data,
            'food_items': FoodItemSerializer(food_items, many=True, context={'request': request}).data,
        })


class CustomerFoodOrderListCreateView(PaginatedFoodListMixin, APIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = FoodOrderSerializer

    @extend_schema(
        tags=['Food - Customers'],
        operation_id='customer_list_food_orders',
        summary='List my food orders',
        parameters=[
            OpenApiParameter('status', str, enum=[choice.value for choice in FoodOrderStatus], required=False),
            OpenApiParameter('past', bool, required=False, description='When true, returns handed over and cancelled orders only.'),
            OpenApiParameter('page', int, required=False),
            OpenApiParameter('page_size', int, required=False),
        ],
        responses={200: FoodOrderListResponseSerializer},
    )
    def get(self, request):
        queryset = FoodOrder.objects.select_related('restaurant', 'restaurant__user', 'courier', 'courier__user').prefetch_related('items').filter(customer=request.user)
        status_filter = (request.query_params.get('status') or '').strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if str(request.query_params.get('past', '')).lower() in ('1', 'true', 'yes'):
            queryset = queryset.filter(status__in=[FoodOrderStatus.HANDED_OVER, FoodOrderStatus.CANCELLED])
        return self.paginated_response(request, queryset)

    @extend_schema(
        tags=['Food - Customers'],
        operation_id='customer_create_food_order',
        summary='Place a food order from a restaurant menu',
        request=FoodOrderCreateSerializer,
        responses={201: FoodOrderSerializer, 400: FoodDetailSerializer},
    )
    def post(self, request):
        serializer = FoodOrderCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            order = serializer.save()
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        order = FoodOrder.objects.select_related('restaurant', 'restaurant__user', 'courier', 'courier__user').prefetch_related('items').get(pk=order.pk)
        return Response(FoodOrderSerializer(order, context={'request': request}).data, status=status.HTTP_201_CREATED)


class CustomerFoodOrderDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(
        tags=['Food - Customers'],
        operation_id='customer_retrieve_food_order',
        summary='Retrieve my food order',
        responses={200: FoodOrderSerializer, 404: FoodDetailSerializer},
    )
    def get(self, request, pk):
        order = get_object_or_404(
            FoodOrder.objects.select_related('restaurant', 'restaurant__user', 'courier', 'courier__user').prefetch_related('items'),
            pk=pk,
            customer=request.user,
        )
        return Response(FoodOrderSerializer(order, context={'request': request}).data)


class CustomerFoodOrderCancelView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(
        tags=['Food - Customers'],
        operation_id='customer_cancel_food_order',
        summary='Cancel my food order',
        request=FoodOrderCancelSerializer,
        responses={200: FoodOrderActionResponseSerializer, 400: FoodDetailSerializer, 404: FoodDetailSerializer},
    )
    def post(self, request, pk):
        order = get_object_or_404(FoodOrder, pk=pk, customer=request.user)
        serializer = FoodOrderCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order = FoodService.cancel_order(order, request.user, FoodCancellationActor.CUSTOMER, serializer.validated_data.get('reason', ''))
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Food order cancelled.', 'order': FoodOrderSerializer(order, context={'request': request}).data})


class CustomerFoodItemReviewView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(
        tags=['Food - Customers'],
        operation_id='customer_review_food_order_item',
        summary='Review one food item from a handed-over order',
        request=FoodItemReviewCreateSerializer,
        responses={201: FoodItemReviewResponseSerializer, 400: FoodDetailSerializer, 404: FoodDetailSerializer},
    )
    def post(self, request, item_pk):
        order_item = get_object_or_404(FoodOrderItem.objects.select_related('order'), pk=item_pk, order__customer=request.user)
        serializer = FoodItemReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            review = FoodService.submit_item_review(order_item, request.user, serializer.validated_data)
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Food item review submitted.', 'review': FoodItemReviewSerializer(review).data}, status=status.HTTP_201_CREATED)


class ProviderCategoryListCreateView(PaginatedFoodListMixin, APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]
    serializer_class = MenuCategorySerializer

    @extend_schema(
        tags=['Food - Provider'],
        operation_id='provider_list_menu_categories',
        summary='List my restaurant menu categories',
        parameters=[OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)],
        responses={200: MenuCategoryListResponseSerializer, 403: FoodDetailSerializer},
    )
    def get(self, request):
        restaurant = get_restaurant_provider_profile(request.user)
        if not restaurant:
            return Response({'detail': 'Restaurant provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        queryset = MenuCategory.objects.filter(restaurant=restaurant).order_by('display_order', 'name')
        return self.paginated_response(request, queryset)

    @extend_schema(
        tags=['Food - Provider'],
        operation_id='provider_create_menu_category',
        summary='Create a menu category for my restaurant',
        request=MenuCategorySerializer,
        responses={201: MenuCategorySerializer, 400: FoodDetailSerializer, 403: FoodDetailSerializer},
    )
    def post(self, request):
        restaurant = get_restaurant_provider_profile(request.user)
        if not restaurant:
            return Response({'detail': 'Restaurant provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = MenuCategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save(restaurant=restaurant)
        return Response(MenuCategorySerializer(category).data, status=status.HTTP_201_CREATED)


class ProviderCategoryDetailView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    def get_object(self, request, pk):
        restaurant = get_restaurant_provider_profile(request.user)
        if not restaurant:
            return None, Response({'detail': 'Restaurant provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        return get_object_or_404(MenuCategory, pk=pk, restaurant=restaurant), None

    @extend_schema(tags=['Food - Provider'], operation_id='provider_retrieve_menu_category', summary='Retrieve my menu category', responses={200: MenuCategorySerializer, 403: FoodDetailSerializer, 404: FoodDetailSerializer})
    def get(self, request, pk):
        category, error = self.get_object(request, pk)
        if error:
            return error
        return Response(MenuCategorySerializer(category).data)

    @extend_schema(tags=['Food - Provider'], operation_id='provider_update_menu_category', summary='Patch my menu category', request=MenuCategorySerializer, responses={200: MenuCategorySerializer, 403: FoodDetailSerializer, 404: FoodDetailSerializer})
    def patch(self, request, pk):
        category, error = self.get_object(request, pk)
        if error:
            return error
        serializer = MenuCategorySerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(MenuCategorySerializer(serializer.save()).data)

    @extend_schema(tags=['Food - Provider'], operation_id='provider_delete_menu_category', summary='Delete my menu category', responses={204: None, 403: FoodDetailSerializer, 404: FoodDetailSerializer})
    def delete(self, request, pk):
        category, error = self.get_object(request, pk)
        if error:
            return error
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProviderFoodItemListCreateView(PaginatedFoodListMixin, APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]
    serializer_class = FoodItemSerializer

    @extend_schema(
        tags=['Food - Provider'],
        operation_id='provider_list_food_items',
        summary='List my restaurant food items',
        parameters=[
            OpenApiParameter('category', int, required=False),
            OpenApiParameter('available_today', bool, required=False),
            OpenApiParameter('page', int, required=False),
            OpenApiParameter('page_size', int, required=False),
        ],
        responses={200: FoodItemListResponseSerializer, 403: FoodDetailSerializer},
    )
    def get(self, request):
        restaurant = get_restaurant_provider_profile(request.user)
        if not restaurant:
            return Response({'detail': 'Restaurant provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        queryset = FoodItem.objects.select_related('category').filter(restaurant=restaurant)
        category_id = request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        available = request.query_params.get('available_today')
        if available is not None:
            queryset = queryset.filter(available_today=str(available).lower() in ('1', 'true', 'yes'))
        return self.paginated_response(request, queryset)

    @extend_schema(
        tags=['Food - Provider'],
        operation_id='provider_create_food_item',
        summary='Create a food item for my restaurant',
        request=FoodItemWriteSerializer,
        responses={201: FoodItemSerializer, 400: FoodDetailSerializer, 403: FoodDetailSerializer},
    )
    def post(self, request):
        restaurant = get_restaurant_provider_profile(request.user)
        if not restaurant:
            return Response({'detail': 'Restaurant provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = FoodItemWriteSerializer(data=request.data, context={'restaurant': restaurant})
        serializer.is_valid(raise_exception=True)
        food_item = serializer.save(restaurant=restaurant)
        return Response(FoodItemSerializer(food_item, context={'request': request}).data, status=status.HTTP_201_CREATED)


class ProviderFoodItemDetailView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    def get_object(self, request, pk):
        restaurant = get_restaurant_provider_profile(request.user)
        if not restaurant:
            return None, None, Response({'detail': 'Restaurant provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        return restaurant, get_object_or_404(FoodItem.objects.select_related('category'), pk=pk, restaurant=restaurant), None

    @extend_schema(tags=['Food - Provider'], operation_id='provider_retrieve_food_item', summary='Retrieve my food item', responses={200: FoodItemSerializer, 403: FoodDetailSerializer, 404: FoodDetailSerializer})
    def get(self, request, pk):
        restaurant, food_item, error = self.get_object(request, pk)
        if error:
            return error
        return Response(FoodItemSerializer(food_item, context={'request': request}).data)

    @extend_schema(tags=['Food - Provider'], operation_id='provider_update_food_item', summary='Patch my food item', request=FoodItemWriteSerializer, responses={200: FoodItemSerializer, 400: FoodDetailSerializer, 403: FoodDetailSerializer, 404: FoodDetailSerializer})
    def patch(self, request, pk):
        restaurant, food_item, error = self.get_object(request, pk)
        if error:
            return error
        serializer = FoodItemWriteSerializer(food_item, data=request.data, partial=True, context={'restaurant': restaurant})
        serializer.is_valid(raise_exception=True)
        return Response(FoodItemSerializer(serializer.save(), context={'request': request}).data)

    @extend_schema(tags=['Food - Provider'], operation_id='provider_delete_food_item', summary='Delete my food item', responses={204: None, 403: FoodDetailSerializer, 404: FoodDetailSerializer})
    def delete(self, request, pk):
        restaurant, food_item, error = self.get_object(request, pk)
        if error:
            return error
        food_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProviderFoodOrderListView(PaginatedFoodListMixin, APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]
    serializer_class = FoodOrderSerializer

    @extend_schema(
        tags=['Food - Provider'],
        operation_id='provider_list_food_orders',
        summary='List orders for my restaurant',
        parameters=[OpenApiParameter('status', str, enum=[choice.value for choice in FoodOrderStatus], required=False), OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)],
        responses={200: FoodOrderListResponseSerializer, 403: FoodDetailSerializer},
    )
    def get(self, request):
        restaurant = get_restaurant_provider_profile(request.user)
        if not restaurant:
            return Response({'detail': 'Restaurant provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        queryset = FoodOrder.objects.select_related('customer', 'restaurant', 'restaurant__user', 'courier', 'courier__user').prefetch_related('items').filter(restaurant=restaurant)
        status_filter = (request.query_params.get('status') or '').strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return self.paginated_response(request, queryset)


class ProviderFoodOrderDetailView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    @extend_schema(tags=['Food - Provider'], operation_id='provider_retrieve_food_order', summary='Retrieve an order for my restaurant', responses={200: FoodOrderSerializer, 403: FoodDetailSerializer, 404: FoodDetailSerializer})
    def get(self, request, pk):
        restaurant = get_restaurant_provider_profile(request.user)
        if not restaurant:
            return Response({'detail': 'Restaurant provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        order = get_object_or_404(FoodOrder.objects.select_related('customer', 'restaurant', 'restaurant__user', 'courier', 'courier__user').prefetch_related('items'), pk=pk, restaurant=restaurant)
        return Response(FoodOrderSerializer(order, context={'request': request}).data)


class ProviderFoodOrderStatusView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    @extend_schema(
        tags=['Food - Provider'],
        operation_id='provider_update_food_order_status',
        summary='Move my restaurant order to the next valid milestone',
        description='Allowed status flow: placed -> confirmed -> in_prep -> kitchen_sealed -> courier_assigned -> in_transit -> handed_over. cancelled is allowed before handover.',
        request=FoodOrderStatusUpdateSerializer,
        responses={200: FoodOrderActionResponseSerializer, 400: FoodDetailSerializer, 403: FoodDetailSerializer, 404: FoodDetailSerializer},
    )
    def post(self, request, pk):
        restaurant = get_restaurant_provider_profile(request.user)
        if not restaurant:
            return Response({'detail': 'Restaurant provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        order = get_object_or_404(FoodOrder, pk=pk, restaurant=restaurant)
        serializer = FoodOrderStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order = FoodService.update_status(
                order,
                restaurant,
                serializer.validated_data['status'],
                actor_user=request.user,
                courier_profile=serializer.validated_data.get('courier_profile'),
            )
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Food order status updated.', 'order': FoodOrderSerializer(order, context={'request': request}).data})


class CourierFoodOrderLocationView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    @extend_schema(
        tags=['Food - Courier'],
        operation_id='courier_update_food_order_location',
        summary='Update my live courier location for an assigned food order',
        request=FoodCourierLocationSerializer,
        responses={200: FoodOrderActionResponseSerializer, 400: FoodDetailSerializer, 403: FoodDetailSerializer, 404: FoodDetailSerializer},
    )
    def post(self, request, pk):
        courier = get_courier_provider_profile(request.user)
        if not courier:
            return Response({'detail': 'Courier provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        order = get_object_or_404(FoodOrder, pk=pk, courier=courier)
        serializer = FoodCourierLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order = FoodService.update_courier_location(order, courier, serializer.validated_data['latitude'], serializer.validated_data['longitude'])
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Courier location updated.', 'order': FoodOrderSerializer(order, context={'request': request}).data})


class SuperAdminFoodOrderListView(PaginatedFoodListMixin, APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    serializer_class = FoodOrderSerializer

    @extend_schema(
        tags=['Food - SuperAdmin'],
        operation_id='admin_list_food_orders',
        summary='List all food orders',
        parameters=[OpenApiParameter('status', str, enum=[choice.value for choice in FoodOrderStatus], required=False), OpenApiParameter('restaurant', int, required=False), OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)],
        responses={200: FoodOrderListResponseSerializer},
    )
    def get(self, request):
        queryset = FoodOrder.objects.select_related('customer', 'restaurant', 'restaurant__user', 'courier', 'courier__user').prefetch_related('items')
        status_filter = (request.query_params.get('status') or '').strip()
        restaurant_id = request.query_params.get('restaurant')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if restaurant_id:
            queryset = queryset.filter(restaurant_id=restaurant_id)
        return self.paginated_response(request, queryset)


class SuperAdminFoodOrderDetailView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(tags=['Food - SuperAdmin'], operation_id='admin_retrieve_food_order', summary='Retrieve a food order', responses={200: FoodOrderSerializer, 404: FoodDetailSerializer})
    def get(self, request, pk):
        order = get_object_or_404(FoodOrder.objects.select_related('customer', 'restaurant', 'restaurant__user', 'courier', 'courier__user').prefetch_related('items'), pk=pk)
        return Response(FoodOrderSerializer(order, context={'request': request}).data)


class SuperAdminFoodOrderPaymentStatusView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(
        tags=['Food - SuperAdmin'],
        operation_id='admin_update_food_order_payment_status',
        summary='Update food order payment status',
        request=FoodPaymentStatusUpdateSerializer,
        responses={200: FoodOrderActionResponseSerializer, 400: FoodDetailSerializer, 404: FoodDetailSerializer},
    )
    def post(self, request, pk):
        order = get_object_or_404(FoodOrder, pk=pk)
        serializer = FoodPaymentStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order = FoodService.update_payment_status(order, serializer.validated_data['payment_status'], total_amount=serializer.validated_data.get('total_amount'))
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Food order payment status updated.', 'order': FoodOrderSerializer(order, context={'request': request}).data})
