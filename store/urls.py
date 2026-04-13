from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('add/', views.cart_add, name='cart_add'),
    path('carrito/', views.cart_summary, name='cart_summary'),
    path('checkout/', views.checkout, name='checkout'),
    path('pago-exitoso/', views.pago_exitoso, name='pago_exitoso'),
    path('pago-fallido/', views.pago_fallido, name='pago_fallido'),
    path('buscar-ajax/', views.buscar_ajax, name='buscar_ajax'),
    path('producto/<int:producto_id>/', views.producto_detalle, name='producto_detalle'),
    path('cart_delete/', views.cart_delete, name='cart_delete'),
    path('procesar-pedido/', views.procesar_pedido, name='procesar_pedido'),
    path('whatsapp/webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),
]