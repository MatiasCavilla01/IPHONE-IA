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
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import re
import json       # <--- ESTA ES LA QUE FALTA
import requests   # <--- También la vas a necesitar para responder mensajes



def index(request):
    todas_las_categorias = Categoria.objects.all()
    categoria_slug = request.GET.get('categoria')
    
    productos = Producto.objects.all()
    categoria_obj = None

    if categoria_slug:
        # Filtramos por el nombre o slug
        productos = Producto.objects.filter(categoria__nombre__iexact=categoria_slug)
        categoria_obj = categoria_slug # O busca el objeto: Categoria.objects.get(nombre=categoria_slug)

    return render(request, 'store/index.html', {
        'categorias': todas_las_categorias,
        'productos': productos,
        'categoria_seleccionada': categoria_obj # Esto activa el IF en el template
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

def router_mensajes(mensaje_usuario):
    mensaje_clean = mensaje_usuario.lower().strip()
    
    if "stock" in mensaje_clean:
        palabras = mensaje_clean.split()
        
        # Caso A: El usuario puso solo "stock"
        if len(palabras) == 1:
            return "¡Hola! ¿De qué producto buscás stock? Decime el nombre (ej: iPhone 13) y te confirmo."

        # Caso B: Buscamos el producto en la DB
        # Filtramos palabras que no son el nombre del producto
        excluir = ["stock", "tenes", "hay", "de", "el", "la", "un", "precio", "vsv", "vcv"]
        busqueda = [p for p in palabras if p not in excluir]

        for p in busqueda:
            # Buscamos en la base de datos de Django
            prod = Producto.objects.filter(nombre__icontains=p).first()
            if prod:
                return (f"¡Sí! De *{prod.nombre}* tenemos {prod.stock} unidades. "
                        f"Precio: ${prod.precio}. ¿Te gustaría comprarlo?")

        return "No encontré ese producto en mi lista. ¿Podrías decirme el nombre exacto?"

    # Si no es stock, va a Gemini
    return llamar_a_gemini(mensaje_usuario)

    
# tools.py (Lógica de negocio)

def crear_pedido_automatico(producto_nombre, cantidad, cliente_whatsapp):
    """
    Busca el producto, verifica stock y crea un pedido en la DB.
    Retorna un mensaje de éxito o error.
    """
    try:
        from .models import Producto, Pedido # Importa tus modelos
        
        producto = Producto.objects.filter(nombre__icontains=producto_nombre).first()
        
        if not producto:
            return f"Lo siento, no encontré el producto '{producto_nombre}'."
        
        if producto.stock < cantidad:
            return f"No tengo stock suficiente de {producto.nombre}. Solo quedan {producto.stock}."

        # Creamos el pedido (esto ya interactúa con tu DB de Django)
        nuevo_pedido = Pedido.objects.create(
            producto=producto,
            cantidad=cantidad,
            telefono_cliente=cliente_whatsapp,
            estado='Pendiente'
        )
        
        # Aquí podrías generar el link de Mercado Pago
        link_pago = f"https://mpago.la/vsv-store-ejemplo-{nuevo_pedido.id}"
        
        return f"¡Pedido creado! ID: {nuevo_pedido.id}. Producto: {producto.nombre}. Link de pago: {link_pago}"
    
    except Exception as e:
        return f"Hubo un error al procesar el pedido: {str(e)}"
    
import google.generativeai as genai
import os

import google.generativeai as genai
from google.generativeai.types import RequestOptions

# 1. Configuramos la API Key con transporte REST para evitar errores de ruta
import requests
import json

def llamar_a_gemini(mensaje_usuario):
    # Tu API Key (Mantenela segura)
    api_key = "AIzaSyDcTdHNH4xDmPYj1T5r3ivoh4J5PubuuzI" 
    
    # URL actualizada al modelo que tenés activo según tu diagnóstico
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={api_key}"
    
    headers = {'Content-Type': 'application/json'}
    
    data = {
        "contents": [{
            "parts": [{"text": f"Eres el asistente de VSV STORE. Responde brevemente a: {mensaje_usuario}"}]
        }]
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        res_json = response.json()
        
        # Log para control en la terminal de VS Code
        print(f"Respuesta Raw de Google: {res_json}")
        
        if response.status_code == 200:
            # Extraemos la respuesta del modelo
            return res_json['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"Error de API ({response.status_code}): {res_json.get('error', {}).get('message')}"
            
    except Exception as e:
        print(f"Error en la llamada: {e}")
        return "Hola! Estamos con mucha demanda en VSV Store, ¿me repetís tu consulta en un momento?"

ACCESS_TOKEN = "EAAbwNepQP9IBRLbghlp7ZB41JeIe2uV8RWLGFAsMmYfPeUTYoZAJi4ICl5p0Pq6PhKIlaqXUzEcZANwkZAtLfkozzqNZCcZCgPdaREfCf3im4ZAXMaHk3VQdljmD62rSBdvf2LsvtsriC9eO0OHueZCg10ztu7adP78WrEyKQ1EeDMTqXLsIZARlY1ngUbKNDG31NQlCzT5ZA9NHf5H1pRQl9tAVNvGEWbTT3A7LeEfpyWR6w2jwLtdjZC1phF5DUifZBcFyvWritRqmnDKtbTZC1OXsonAZDZD"
PHONE_NUMBER_ID = "1101551966368735"
VERSION = "v25.0" # O la que diga tu panel

def enviar_mensaje_whatsapp(telefono, texto):
    # --- LIMPIEZA DE NÚMERO PARA ARGENTINA ---
    # Si el número empieza con 549, le sacamos el 9 para probar
    if telefono.startswith("549"):
        # Esto lo transforma de 5493544... a 543544...
        telefono_limpio = "54" + telefono[3:]
    else:
        telefono_limpio = telefono

    url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": telefono_limpio, # <--- Usamos el número limpio
        "type": "text",
        "text": {"body": texto},
    }
    
    response = requests.post(url, headers=headers, json=data)
    print(f"Enviando a: {telefono_limpio} | Respuesta Meta: {response.json()}")
    return response.json()


@csrf_exempt
def whatsapp_webhook(request):
    if request.method == 'GET':
        return HttpResponse(request.GET.get('hub.challenge'), status=200)

    elif request.method == 'POST':
        data = json.loads(request.body)
        try:
            # 1. Extraer info del mensaje
            value = data['entry'][0]['changes'][0]['value']
            if 'messages' not in value:
                return HttpResponse('EVENT_RECEIVED', status=200)

            mensaje_usuario = value['messages'][0]['text']['body']
            numero_cliente = value['messages'][0]['from']
            
            print(f"--- NUEVO MENSAJE: {mensaje_usuario} ---")

            # 2. BUSCADOR EN BASE DE DATOS (Cerebro Lógico)
            # 1. Extraemos y limpiamos el mensaje
            mensaje_lower = mensaje_usuario.lower().strip()

            # 2. Lógica de "Portero" para Stock
            respuesta_final = None

            if "stock" in mensaje_lower:
                palabras = mensaje_lower.split()
                # Quitamos la palabra 'stock' para ver si queda el nombre de un producto
                busqueda_db = [p for p in palabras if p not in ["stock", "tenes", "hay", "de", "el"]]

                if not busqueda_db:
                    # CASO: El cliente dijo solo "stock" o "tenes stock?"
                    respuesta_final = (
                        "¡Hola! En *VSV STORE* tenemos de todo. 😎\n\n"
                        "¿Querés que te pase la **lista completa** de productos o estás buscando **alguno en especial** (ej: iPhone, AirPods)?"
                    )
                else:
                    # CASO: El cliente ya especificó algo, ej: "stock iphone"
                    for p in busqueda_db:
                        if len(p) > 2:
                            prod = Producto.objects.filter(nombre__icontains=p).first()
                            if prod:
                                respuesta_final = (
                                    f"¡Sí! Del *{prod.nombre}* nos quedan {prod.stock} unidades. "
                                    f"Precio: ${prod.precio}. ¿Te lo reservo?"
                                )
                                break
                    
                    if not respuesta_final:
                        respuesta_final = "No encontré ese modelo exacto, pero tengo otros iPhones y accesorios. ¿Querés ver la lista completa?"

            # 3. Respuesta para la "Lista Completa"
            if "lista completa" in mensaje_lower or "todo el stock" in mensaje_lower:
                productos = Producto.objects.filter(stock__gt=0)[:10] # Traemos los primeros 10 con stock
                lista_texto = "Libre de elegir! Acá tenés lo disponible:\n"
                for p in productos:
                    lista_texto += f"• {p.nombre} - ${p.precio}\n"
                respuesta_final = lista_texto

            # 4. Si después de todo lo anterior respuesta_final sigue siendo None, va a Gemini
            if not respuesta_final:
                respuesta_final = llamar_a_gemini(mensaje_usuario)

            # 4. ENVIAR RESPUESTA
            enviar_mensaje_whatsapp(numero_cliente, respuesta_final)

        except Exception as e:
            print(f"Error en el proceso: {e}")

        return HttpResponse('EVENT_RECEIVED', status=200)

def registrar_pedido_en_db(producto_nombre, cantidad):
    """
    Esta función la llamará Gemini automáticamente.
    """
    try:
        from .models import Producto, Pedido
        prod = Producto.objects.filter(nombre__icontains=producto_nombre).first()
        if prod and prod.stock >= int(cantidad):
            # Aquí creas el pedido en tu PostgreSQL
            # Pedido.objects.create(producto=prod, cantidad=cantidad, ...)
            return f"EXITO: Pedido registrado de {cantidad} {prod.nombre}. Total: ${prod.precio * int(cantidad)}"
        return "ERROR: No hay stock suficiente o producto no encontrado."
    except Exception as e:
        return f"ERROR: {str(e)}"