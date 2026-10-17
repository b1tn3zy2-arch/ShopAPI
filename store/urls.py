from django.urls import path
from . import views

urlpatterns = [
    path('', views.products_list, name='products_list'),
    path('products/', views.products_list, name='products_list'),
    path('products/add/', views.product_add, name='product_add'),
    path('products/<int:pk>/price/', views.product_price, name='product_price'),
    path('orders/create/', views.order_create, name='order_create'),
    path('orders/<int:order_id>/add-item/', views.order_add_item, name='order_add_item'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('customers/<int:pk>/orders/', views.customer_orders, name='customer_orders'),
    path('stats/categories/', views.category_stats, name='category_stats'),
    path('discount/', views.discount_view, name='discount'),
]