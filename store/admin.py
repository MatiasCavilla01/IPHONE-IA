from django.contrib import admin
from .models import Categoria, Producto, Variante
from django.utils.html import format_html

# 1. Definimos cómo se van a ver las variantes dentro del producto
class VarianteInline(admin.TabularInline):
    model = Variante
    extra = 1 # Fila vacía para agregar una nueva variante rápido
    # Asegurate que estos nombres coincidan EXACTAMENTE con los de tu models.py
    fields = ['color', 'capacidad', 'precio_adicional'] 

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    # Columnas en la lista principal
    list_display = ('mostrar_foto', 'nombre', 'categoria', 'precio')
    
    # Filtros y Buscador
    list_filter = ('categoria',)
    search_fields = ('nombre', 'descripcion')
    
    # --- LA MAGIA ESTÁ ACÁ ---
    # Esto le dice a Django: "Cuando edites un Producto, mostrame sus Variantes abajo"
    inlines = [VarianteInline]
    
    # Función para la miniatura de la foto
    def mostrar_foto(self, obj):
        if obj.imagen:
            return format_html('<img src="{}" style="width: 50px; height: 50px; border-radius: 8px; object-fit: cover;" />', obj.imagen.url)
        return "Sin imagen"
    
    mostrar_foto.short_description = 'Imagen'

# Si querés poder ver las variantes también por separado en el menú lateral,
# podés dejar esta línea. Si no, borrala y solo las verás dentro de cada producto.
admin.site.register(Variante)