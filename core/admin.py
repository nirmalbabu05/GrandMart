from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, StoreSettings, Warehouse, Category, Unit, 
    Product, Supplier, DeliverySchedule, ProductBatch, 
    Order, OrderItem
)

# 1. Register Custom User
admin.site.register(User, UserAdmin)

# 2. Register Master Settings
admin.site.register(StoreSettings)
admin.site.register(Warehouse)

# 3. Register Product Master
admin.site.register(Category)
admin.site.register(Unit)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'pack_size', 'selling_price', 'stock_quantity', 'is_active')
    search_fields = ('name', 'barcode')
    list_filter = ('category', 'is_active')

# 4. Register Supplier & Inventory
admin.site.register(Supplier)
admin.site.register(DeliverySchedule)

@admin.register(ProductBatch)
class ProductBatchAdmin(admin.ModelAdmin):
    list_display = ('product', 'batch_number', 'quantity_available', 'received_date')
    search_fields = ('batch_number', 'product__name')

# 5. Register Sales (POS) with Inline Items
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'customer_name', 'grand_total', 'payment_method', 'created_at')
    search_fields = ('invoice_number', 'customer_phone')
    list_filter = ('payment_method',)
    inlines = [OrderItemInline]