from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

# ==========================================
# 0. CUSTOM USER MODEL
# ==========================================
class User(AbstractUser):
    role = models.CharField(max_length=20, default='Admin')

# ==========================================
# 1. MASTER SETTINGS & CONFIGURATION
# ==========================================
class StoreSettings(models.Model):
    store_name = models.CharField(max_length=255, default="GrandMart Supermarket")
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    gst_number = models.CharField(max_length=50, blank=True, null=True)
    logo = models.ImageField(upload_to='store_logos/', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.store_name

class Warehouse(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255, blank=True, null=True)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

# ==========================================
# 2. PRODUCT MASTER (CATEGORIES, UNITS, ITEMS)
# ==========================================
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

class Unit(models.Model):
    name = models.CharField(max_length=50) 
    short_name = models.CharField(max_length=20) 
    
    def __str__(self):
        return self.short_name

class Product(models.Model):
    name = models.CharField(max_length=255, verbose_name="Product Name")
    image = models.ImageField(upload_to='product_images/', blank=True, null=True)
    image_url = models.URLField(max_length=1000, blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True)
    
    pack_size = models.CharField(max_length=50, default="1 Pc", verbose_name="Size/Qty (e.g., 5KG, 2L)")
    mrp_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00) 
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0.00)
    
    barcode = models.CharField(max_length=100, unique=True, null=True, blank=True)
    stock_quantity = models.IntegerField(default=0)
    
    reorder_level = models.IntegerField(default=10, help_text="Alert if stock goes below this")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.pack_size})"

# ==========================================
# 3. SUPPLIER & INVENTORY MANAGEMENT
# ==========================================
class Supplier(models.Model):
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    gst_number = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class DeliverySchedule(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Arrived', 'Arrived'),
        ('Cancelled', 'Cancelled'),
    ]
    
    delivery_id = models.CharField(max_length=20, unique=True, verbose_name="Schedule ID")
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="deliveries")
    expected_date = models.DateField()
    expected_items = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.delivery_id} - {self.supplier.name}"

class ProductBatch(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='batches')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    batch_number = models.CharField(max_length=100)
    manufacturing_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    quantity_received = models.IntegerField()
    quantity_available = models.IntegerField()
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    received_date = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name_plural = "Product Batches"

    def __str__(self):
        return f"{self.product.name} - {self.batch_number}"

# ==========================================
# 4. SALES & BILLING (POS & WEB)
# ==========================================
class Order(models.Model):
    PAYMENT_CHOICES = [
        ('Cash', 'Cash'),
        ('Card', 'Card'),
        ('UPI', 'UPI'),
        ('COD', 'Cash on Delivery'), 
        ('Online', 'Online Payment'), 
    ]
    
    ORDER_TYPE_CHOICES = [
        ('POS', 'POS Billing'),
        ('WEB', 'Web Store Order'),
    ]
    
    STATUS_CHOICES = [
        ('Completed', 'Completed'), 
        ('Pending', 'Pending'), 
        ('Processing', 'Processing'), 
        ('Packing', 'Packing'), # 🌟 NEW: Added to match web_orders.html
        ('Out for Delivery', 'Out for Delivery'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    ]
    
    invoice_number = models.CharField(max_length=50, unique=True)
    
    # WHO CREATED THE ORDER?
    order_type = models.CharField(max_length=10, choices=ORDER_TYPE_CHOICES, default='POS')
    cashier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='pos_orders')
    customer_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='web_orders') 
    
    # CUSTOMER DETAILS
    customer_name = models.CharField(max_length=255, blank=True, null=True, default="Walk-in Customer")
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    shipping_address = models.TextField(blank=True, null=True) 
    
    # MONEY MATTERS
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # STATUS & TRACKING
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='Cash')
    is_paid = models.BooleanField(default=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Completed')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.invoice_number} | {self.order_type} | {self.status}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product.name if self.product else 'Deleted Product'}"