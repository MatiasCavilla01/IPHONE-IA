from django.db import models

# Create your models here.
from django.db import models

class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(max_length=150, unique=True, null=True, blank=True)
    orden = models.IntegerField(default=0) # Para que decidas qué sección va arriba

    def __str__(self):
        return self.nombre
    
    class Meta:
        verbose_name_plural = 'Categorias'

class Producto(models.Model):
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, related_name='productos')
    # ... resto de tus campos (precio, imagen, stock) ...
    nombre = models.CharField(max_length=200) # Ej: iPhone 15 Pro
    descripcion = models.TextField()
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    imagen = models.ImageField(upload_to='productos/')
    stock = models.IntegerField(default=0)

    def __str__(self):
        return self.nombre

class Variante(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='variantes')
    capacidad = models.CharField(max_length=50) # Ej: 128GB, 256GB
    color = models.CharField(max_length=50)     # Ej: Titanio Natural
    precio_adicional = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.producto.nombre} - {self.capacidad} - {self.color}"
    
class Pedido(models.Model):
    usuario = models.ForeignKey('auth.User', on_delete=models.CASCADE, null=True, blank=True)
    nombre_completo = models.CharField(max_length=250)
    email = models.EmailField(max_length=250)
    total_pagado = models.DecimalField(max_digits=10, decimal_places=2)
    pagado = models.BooleanField(default=False) # <--- Vital para Mercado Pago
    fecha_pedido = models.DateTimeField(auto_now_add=True)
    mercado_pago_id = models.CharField(max_length=250, blank=True, null=True)

    def __str__(self):
        return f"Pedido {self.id} - {self.nombre_completo}"

class ElementoPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveBigIntegerField(default=1)
    precio = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Item {self.id} del pedido {self.pedido.id}"