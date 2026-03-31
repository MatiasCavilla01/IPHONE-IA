from decouple import config
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from .cart import Cart
import mercadopago
from django.conf import settings
# Create your views here.
from .models import Producto, Categoria, models
from django.db.models import Prefetch
from django.shortcuts import redirect
import urllib.parse
from django.http import JsonResponse

def index(request):
    # Traemos las categorías ordenadas y sus productos de un solo golpe (optimizado)
    categorias = Categoria.objects.all().order_by('orden').prefetch_related('productos')
    
    return render(request, 'store/index.html', {
        'categorias': categorias
    })

def cart_add(request):
    cart = Cart(request)
    if request.POST.get('action') == 'post':
        product_id = int(request.POST.get('product_id'))
        product_qty = int(request.POST.get('product_qty'))
        product = get_object_or_404(Producto, id=product_id)
        cart.add(product=product, qty=product_qty)
        
        cart_quantity = cart.__len__()
        response = JsonResponse({'qty': cart_quantity})
        return response
    
def cart_summary(request):
    cart = Cart(request)
    
    # Calculamos el total (esto ya lo tenías perfecto)
    total = sum(float(item['price']) * item['qty'] for item in cart.cart.values())
    
    # --- LA MAGIA NUEVA ---
    # 1. Sacamos todos los IDs de los productos que están en la sesión
    producto_ids = cart.cart.keys()
    
    # 2. Buscamos esos productos reales en la base de datos
    productos_reales = Producto.objects.filter(id__in=producto_ids)
    
    # 3. Armamos una lista limpia combinando el producto real + la cantidad de la sesión
    items_carrito = []
    for producto in productos_reales:
        prod_id_str = str(producto.id)
        if prod_id_str in cart.cart:
            items_carrito.append({
                'producto': producto,
                'cantidad': cart.cart[prod_id_str]['qty']
            })

    # Ahora sí le mandamos al HTML la lista completa y el total
    return render(request, 'store/cart_summary.html', {
        'items_carrito': items_carrito, 
        'total': total
    })

def checkout(request):
    # 1. Inicializar Mercado Pago con tu Token del .env
    sdk = mercadopago.SDK(config('MP_ACCESS_TOKEN'))
    
    cart = Cart(request)
    items_mp = []

    # 2. Armar la lista de productos para Mercado Pago
    for id, item in cart.cart.items():
        producto = Producto.objects.get(id=id)
        items_mp.append({
            "title": producto.nombre,
            "quantity": int(item['qty']),
            "unit_price": float(item['price']),
            "currency_id": "ARS" # O tu moneda
        })
    # 3. Estructura simplificada al máximo para que no falle
    preference_data = {
        "items": items_mp,
        "back_urls": {
            "success": "http://127.0.0.1:8000/",
            "failure": "http://127.0.0.1:8000/",
            "pending": "http://127.0.0.1:8000/"
        },
        # Comentamos el auto_return para probar si el error desaparece
        # "auto_return": "approved", 
    }

    preference_response = sdk.preference().create(preference_data)
    preference = preference_response["response"]
    
    print("RESPUESTA COMPLETA MP:", preference) # Esto nos dará la clave final en la terminal
    total = sum(float(item['price']) * item['qty'] for item in cart.cart.values())
    
    return render(request, 'store/checkout.html', {
        'preference_id': preference['id'],
        'total_checkout': total  # <--- Agrega esto
    })

def pago_exitoso(request):
    cart = Cart(request)
    
    # Recorremos el carrito para descontar stock
    for id, item in cart.cart.items():
        producto = Producto.objects.get(id=id)
        producto.stock -= int(item['qty']) # Restamos la cantidad comprada
        producto.save() # Guardamos el cambio en PostgreSQL
    
    # Vaciamos el carrito
    request.session['session_key'] = {}
    request.session.modified = True
    
    return render(request, 'store/pago_exitoso.html')

from django.db import models
from django.db.models import Prefetch

def buscar_ajax(request):
    query = request.GET.get('search', '')
    categoria_id_str = request.GET.get('categoria_id', None)
    
    # 1. Empezamos con TODAS las categorías
    categorias = Categoria.objects.all().order_by('orden')
    
    # 2. FILTRO POR CATEGORÍA (Click en Sidebar)
    # Verificamos si existe y si no es "todas"
    if categoria_id_str and categoria_id_str != 'todas':
        try:
            # Forzamos a que sea un número (Integer)
            categoria_id = int(categoria_id_str)
            # Filtramos la categoría
            categorias = categorias.filter(id=categoria_id)
        except ValueError:
            # Si alguien manda algo raro (ej: ?categoria_id=hola), ignoramos
            pass

    # 3. FILTRO POR TEXTO (Buscador)
    if query:
        productos_filtrados = Producto.objects.filter(
            models.Q(nombre__icontains=query) | 
            models.Q(descripcion__icontains=query)
        )
        categorias = categorias.filter(
            productos__in=productos_filtrados
        ).distinct().prefetch_related(
            Prefetch('productos', queryset=productos_filtrados)
        )
    else:
        # Si NO hay texto, pero SI hay categoría, tenemos que asegurarnos
        # de cargar los productos de ESA categoría
        categorias = categorias.prefetch_related('productos')

    return render(request, 'store/product_list_partial.html', {
        'categorias': categorias,
        'query': query
    })
from django.shortcuts import render, get_object_or_404
# Recordá que ya tenés importado Producto

def producto_detalle(request, producto_id):
    # Trae el producto o da un error 404 si no existe
    producto = get_object_or_404(Producto, id=producto_id)
    variantes = producto.variantes.all()
    
    return render(request, 'store/producto_detalle.html', {
        'producto': producto,'variantes': variantes
    })

def cart_delete(request):
    cart = Cart(request) # Instanciamos el carrito
    
    # Si la petición es POST y viene del AJAX
    if request.POST.get('action') == 'post':
        # Agarramos el ID del producto que nos mandó el script
        product_id = int(request.POST.get('product_id'))
        
        # Llamamos a la función de eliminar de tu clase Cart
        # (A veces en los tutoriales le ponen .delete(), .remove() o .eliminar())
        cart.delete(product=product_id)
        
        # Respondemos con un JSON diciendo que todo salió OK
        response = JsonResponse({'status': 'Producto eliminado'})
        return response
    
import urllib.parse
from django.shortcuts import redirect
# Asegurate de tener importado Producto si vas a buscar los nombres
from .models import Producto 

def procesar_pedido(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        whatsapp_cliente = request.POST.get('whatsapp')
        direccion = request.POST.get('direccion')
        metodo = request.POST.get('metodo')
        
        cart = Cart(request)
        
        # 1. Calculamos el total
        total = sum(float(item['price']) * item['qty'] for item in cart.cart.values())
        
        # --- OPCIÓN A: WHATSAPP ---
        if metodo == 'whatsapp':
            mensaje = f"¡Hola VSV Store! 👋\n\n"
            mensaje += f"Soy *{nombre}* y quiero confirmar mi pedido:\n\n"
            mensaje += "📦 *DETALLE DEL PEDIDO:*\n"
            
            for key, item in cart.cart.items():
                try:
                    p = Producto.objects.get(id=key)
                    nombre_prod = p.nombre
                except:
                    nombre_prod = f"Producto ID: {key}"
                
                subtotal_item = float(item['price']) * item['qty']
                mensaje += f"• {item['qty']}x {nombre_prod} - ${subtotal_item}\n"
            
            mensaje += f"\n💰 *TOTAL A PAGAR: ${total}*\n"
            mensaje += f"📍 *ENTREGA EN:* {direccion}\n"
            mensaje += f"📞 *CONTACTO:* {whatsapp_cliente}\n\n"
            mensaje += "¿Me pasan los datos para la transferencia? ¡Gracias!"

            mensaje_url = urllib.parse.quote(mensaje)
            
            # Usamos tu número de Traslasierra (543544630650)
            url_final = f"https://wa.me/543544630650?text={mensaje_url}"
            
            # Limpiamos el carrito (asegurate de tener el método .clear() en cart.py)
            try:
                cart.clear()
            except:
                pass # Por si todavía no definiste el método clear
            
            return redirect(url_final)

        # --- OPCIÓN B: MERCADO PAGO ---
        elif metodo == 'mercadopago':
            # 1. Tu Token (Asegurate que sea el de PRUEBA si usás tarjetas de prueba)
            sdk = mercadopago.SDK("TEST-8392184819426096-032819-2519e0f6c2cfa533c65cf9d348e76af5-190883069")

            # 2. Armamos los productos
            items_mp = []
            for key, item in cart.cart.items():
                p = Producto.objects.get(id=key)
                items_mp.append({
                    "title": p.nombre,
                    "quantity": int(item['qty']),
                    "unit_price": float(item['price']),
                    "currency_id": "ARS"
                })

            # 3. La Preferencia (Simplificada al máximo como antes)
            preference_data = {
                "items": items_mp,
                "payer": {
                    "name": nombre,
                    "email": "test_user_vsv@test.com", # Email genérico para que no falle
                },
                "back_urls": {
                    # Usamos strings directos para evitar errores de construcción
                    "success": "http://127.0.0.1:8000/pago-exitoso/",
                    "failure": "http://127.0.0.1:8000/pago-fallido/",
                    "pending": "http://127.0.0.1:8000/pago-fallido/",
                },
                # COMENTAMOS ESTO PARA QUE NO TRABE LA PETICIÓN
                # "auto_return": "approved", 
                "binary_mode": True,
            }

            # 4. Crear y Redirigir
            preference_response = sdk.preference().create(preference_data)
            
            # DEBUGEAR: Miramos qué nos contesta MP en la terminal
            if preference_response["status"] == 201 or preference_response["status"] == 200:
                print("¡Preferencia creada con éxito!")
                return redirect(preference_response["response"]["init_point"])
            else:
                print("DETALLE DEL ERROR:", preference_response["response"])
                return redirect('cart_summary')

def pago_fallido(request):
    return render(request, 'store/pago_fallido.html')

def api_productos(request):
    # Solo permitimos que el bot entre con una clave secreta
    api_key = request.GET.get('key')
    if api_key != "1234567898":
        return JsonResponse({'error': 'No autorizado'}, status=403)

    productos = Producto.objects.all().values('id', 'nombre', 'precio', 'stock')
    return JsonResponse(list(productos), safe=False)