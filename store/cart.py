from django.conf import settings


class Cart():
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get('session_key')
        if 'session_key' not in request.session:
            cart = self.session['session_key'] = {}
        self.cart = cart

    def add(self, product, qty):
        product_id = str(product.id)
        if product_id in self.cart:
            self.cart[product_id]['qty'] = int(qty)
        else:
            self.cart[product_id] = {'price': str(product.precio), 'qty': int(qty)}
        self.session.modified = True

    def __len__(self):
        return sum(item['qty'] for item in self.cart.values())
    
    def clear(self):
        # Borra el carrito de la sesión
        del self.session['session_key']

    def delete(self, product):
        product_id = str(product)
        if product_id in self.cart:
            del self.cart[product_id]
            
        self.session.modified = True # ¡Esto es clave para que Django guarde el cambio!
