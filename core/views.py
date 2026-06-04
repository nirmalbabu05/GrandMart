import json
import csv
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, F, Q
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.contrib.auth import get_user_model, authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from functools import wraps

from .models import Product, Order, OrderItem, ProductBatch, Category, Unit, Supplier, Warehouse, StoreSettings, DeliverySchedule

from django.views.decorators.clickjacking import xframe_options_sameorigin

User = get_user_model()

# ==========================================
# 🛡️ CUSTOM SECURITY DECORATOR
# ==========================================
def admin_only(view_func):
    """
    Ithu Admin-a mattum ulla vidum. Cashier click panna, POS Terminal-kku redirect aagiduvaanga.
    """
    @wraps(view_func)
    def wrapper_func(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        else:
            return redirect('pos_terminal')
    return wrapper_func


# ==========================================
# 🔑 AUTHENTICATION VIEWS
# ==========================================
def user_login(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect('erp_dashboard')
        else:
            return redirect('pos_terminal')
        
    error_msg = None
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        
        user = authenticate(request, username=u, password=p)
        
        if user is not None:
            login(request, user)
            if user.is_superuser:
                return redirect('erp_dashboard')
            else:
                return redirect('pos_terminal')
        else:
            error_msg = "Invalid Username or Password!"
            
    return render(request, 'erp/login.html', {'error': error_msg})

def user_logout(request):
    logout(request)
    return redirect('login')


# ==========================================
# 🏪 ERP MODULES (Admin Only Modules)
# ==========================================
@login_required(login_url='login')
@admin_only
def erp_dashboard(request):
    today = timezone.now().date()
    
    total_products = Product.objects.filter(is_active=True).count()
    low_stock_items = Product.objects.filter(stock_quantity__lte=F('reorder_level'), is_active=True)[:5]
    low_stock_count = Product.objects.filter(stock_quantity__lte=F('reorder_level'), is_active=True).count()
    
    total_orders = Order.objects.filter(created_at__date=today).count()
    
    revenue_dict = Order.objects.filter(created_at__date=today).aggregate(Sum('grand_total'))
    revenue_today = revenue_dict['grand_total__sum'] or 0

    chart_labels = []
    chart_data = []
    
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        chart_labels.append(day.strftime('%a'))
        daily_total = Order.objects.filter(created_at__date=day).aggregate(Sum('grand_total'))['grand_total__sum'] or 0
        chart_data.append(float(daily_total))

    context = {
        'total_products': total_products, 
        'low_stock_count': low_stock_count,
        'total_orders': total_orders, 
        'revenue_today': revenue_today,
        'low_stock_items': low_stock_items,
        'chart_labels': json.dumps(chart_labels), 
        'chart_data': json.dumps(chart_data),
    }
    return render(request, 'erp/dashboard.html', context)

@login_required(login_url='login')
@admin_only
def general_master(request):
    if not request.headers.get('HX-Request') and request.method == 'GET':
        return redirect('erp_dashboard')
        
    store, created = StoreSettings.objects.get_or_create(id=1)
    success_msg = False
    
    if request.method == 'POST':
        store.store_name = request.POST.get('store_name', store.store_name)
        store.gst_number = request.POST.get('gst_number', '')
        store.phone = request.POST.get('store_phone', '')
        store.address = request.POST.get('store_address', '')
        store.save()
        success_msg = True 
        
    return render(request, 'erp/general_master.html', {
        'store': store, 
        'success': success_msg
    })

@login_required(login_url='login')
@admin_only
def categories_units(request):
    if not request.headers.get('HX-Request') and request.method == 'GET':
        return redirect('erp_dashboard')
        
    if request.method == 'POST':
        if 'name' in request.POST and 'short_name' not in request.POST:
            Category.objects.create(name=request.POST.get('name'))
        elif 'short_name' in request.POST:
            Unit.objects.create(
                name=request.POST.get('name'), 
                short_name=request.POST.get('short_name')
            )

    return render(request, 'erp/categories_units.html', {
        'categories': Category.objects.all(), 
        'units': Unit.objects.all()
    })

@login_required(login_url='login')
@admin_only
def store_master(request):
    if not request.headers.get('HX-Request') and request.method == 'GET':
        return redirect('erp_dashboard')
        
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            category_id = request.POST.get('category')
            barcode = request.POST.get('barcode')
            image = request.FILES.get('image')
            image_url = request.POST.get('image_url') # ADDED
            
            if not barcode or barcode.strip() == "":
                barcode = None
                
            unit_id = request.POST.get('unit')
            pack_size = request.POST.get('pack_size', '1 Pc')
            mrp_price = request.POST.get('mrp_price') or 0
            selling_price = request.POST.get('selling_price') or 0
            
            category = Category.objects.get(id=category_id)
            unit = Unit.objects.get(id=unit_id) if unit_id else None
            
            Product.objects.create(
                name=name, 
                category=category, 
                barcode=barcode, 
                unit=unit,
                pack_size=pack_size,
                mrp_price=mrp_price,
                selling_price=selling_price,
                image=image, # ADDED
                image_url=image_url # ADDED
            )
        except Exception as e:
            print(f"Error saving product: {e}") 
        
    return render(request, 'erp/store_master.html', {
        'products': Product.objects.all().order_by('-id'), 
        'categories': Category.objects.all(), 
        'units': Unit.objects.all()
    })


@login_required(login_url='login')
@admin_only
def received_goods(request):
    if not request.headers.get('HX-Request') and request.method == 'GET':
        return redirect('erp_dashboard')
        
    if not Warehouse.objects.exists():
        Warehouse.objects.create(name="Main Godown", location="Main Branch")
        
    if not Supplier.objects.exists():
        Supplier.objects.create(name="Default Supplier", contact_person="Owner")

    if request.method == 'POST':
        try:
            supplier_id = request.POST.get('supplier')
            warehouse_id = request.POST.get('warehouse')
            supplier = Supplier.objects.get(id=supplier_id)
            warehouse = Warehouse.objects.get(id=warehouse_id)
            
            bulk_text = request.POST.get('bulk_data', '').strip()
            
            with transaction.atomic():
                # 1. Excel Smart Paste Logic
                if bulk_text:
                    lines = bulk_text.split('\n')
                    for line in lines:
                        if not line.strip():
                            continue 
                        cols = line.split('\t')
                        
                        if len(cols) >= 3:
                            p_name = cols[0].strip()
                            batch_no = cols[1].strip()
                            try:
                                qty = int(cols[2].strip())
                            except ValueError:
                                qty = 0
                            
                            exp_date = cols[3].strip() if len(cols) >= 4 and cols[3].strip() else None
                            
                            if qty <= 0:
                                continue
                                
                            product = Product.objects.filter(name__iexact=p_name).first()
                            
                            if product:
                                batch, created = ProductBatch.objects.get_or_create(
                                    product=product,
                                    batch_number=batch_no,
                                    defaults={
                                        'supplier': supplier,
                                        'quantity_received': qty,
                                        'quantity_available': qty,
                                        'expiry_date': exp_date,
                                        'purchase_price': product.purchase_price or 0.00
                                    }
                                )
                                if not created:
                                    batch.quantity_available += qty
                                    batch.quantity_received += qty
                                    if exp_date:
                                        batch.expiry_date = exp_date
                                    batch.save()
                                    
                                product.stock_quantity += qty
                                product.save()
                
                # 2. Manual Grid Logic
                else:
                    product_ids = request.POST.getlist('product[]')
                    batch_numbers = request.POST.getlist('batch_number[]')
                    quantities = request.POST.getlist('quantity[]')
                    expiry_dates = request.POST.getlist('expiry_date[]')
                    
                    for i in range(len(product_ids)):
                        p_id = product_ids[i]
                        batch_no = batch_numbers[i].strip()
                        qty = int(quantities[i] or 0)
                        exp_date = expiry_dates[i] or None
                        
                        if not p_id or qty <= 0:
                            continue
                            
                        product = Product.objects.get(id=p_id)
                        
                        batch, created = ProductBatch.objects.get_or_create(
                            product=product,
                            batch_number=batch_no,
                            defaults={
                                'supplier': supplier,
                                'quantity_received': qty,
                                'quantity_available': qty,
                                'expiry_date': exp_date if exp_date else None,
                                'purchase_price': product.purchase_price or 0.00
                            }
                        )
                        
                        if not created:
                            batch.quantity_available += qty
                            batch.quantity_received += qty
                            if exp_date:
                                batch.expiry_date = exp_date
                            batch.save()
                            
                        product.stock_quantity += qty
                        product.save()
                        
        except Exception as e:
            print(f"Error processing received goods: {e}") 

    # THE FIX: Split products into Out of Stock and In Stock
    out_of_stock = Product.objects.filter(is_active=True, stock_quantity__lte=0).order_by('name')
    in_stock = Product.objects.filter(is_active=True, stock_quantity__gt=0).order_by('name')

    return render(request, 'erp/received_goods.html', {
        'suppliers': Supplier.objects.all(), 
        'warehouses': Warehouse.objects.all(), 
        'out_of_stock': out_of_stock,
        'in_stock': in_stock,
        'recent_stocks': ProductBatch.objects.all().order_by('-id')[:20]
    })

@login_required(login_url='login')
def stock_balance(request):
    if not request.headers.get('HX-Request') and request.method == 'GET':
        return redirect('erp_dashboard') if request.user.is_superuser else redirect('pos_terminal')
        
    batches = ProductBatch.objects.select_related('product').filter(quantity_available__gt=0).order_by('product__name')
    
    total_qty = sum(batch.quantity_available for batch in batches)
    total_value = sum(batch.quantity_available * batch.product.selling_price for batch in batches)
    
    context = {
        'batches': batches,
        'total_stock_qty': total_qty,
        'low_stock_count': batches.filter(quantity_available__lte=10).count(),
        'total_inventory_value': total_value
    }
    return render(request, 'erp/stock_balance.html', context)

@login_required(login_url='login')
@admin_only
def transfer_goods(request):
    if not request.headers.get('HX-Request') and request.method == 'GET':
        return redirect('erp_dashboard')

    return render(request, 'erp/transfer_goods.html', {
        'products': Product.objects.filter(is_active=True), 
        'warehouses': Warehouse.objects.all(),
        'batches': ProductBatch.objects.filter(quantity_available__gt=0).order_by('-id')[:10],
    })


# ==========================================
# 🛒 CASHIER ACCESSIBLE MODULES (No @admin_only)
# ==========================================
@login_required(login_url='login')
def pos_terminal(request):
    if not request.headers.get('HX-Request') and request.method == 'GET': 
        if request.user.is_superuser:
            return redirect('erp_dashboard')
        else:
            return render(request, 'erp/pos_terminal.html', {
                'products': Product.objects.filter(is_active=True), 
                'categories': Category.objects.all()
            })
            
    if request.method == 'POST':
        data = json.loads(request.body)
        cart = data.get('cart', {})
        
        with transaction.atomic():
            # 1. SECURITY CHECK: Validate stock before creating the bill
            for product_id, item in cart.items():
                product = Product.objects.get(id=product_id)
                if product.stock_quantity < item['qty']:
                    return JsonResponse({
                        'status': 'error', 
                        'message': f"Out of Stock Error: '{product.name}' only has {product.stock_quantity} items left!"
                    })

            # 2. Proceed to Billing if stock is available
            total_amount = sum(item['price'] * item['qty'] for item in cart.values())
            order = Order.objects.create(grand_total=total_amount, cashier=request.user, invoice_number=f"TMP-{timezone.now().timestamp()}")
            order.invoice_number = f"INV-{order.id:06d}"
            order.save()
            
            for product_id, item in cart.items():
                qty_to_deduct = item['qty']
                
                # Update main product stock
                product = Product.objects.get(id=product_id)
                product.stock_quantity -= qty_to_deduct
                product.save()
                
                # Update Batch logic (FIFO deduction)
                batches = ProductBatch.objects.filter(product_id=product_id, quantity_available__gt=0).order_by('id')
                for batch in batches:
                    if qty_to_deduct <= 0:
                        break
                        
                    if batch.quantity_available >= qty_to_deduct:
                        batch.quantity_available -= qty_to_deduct
                        batch.save()
                        qty_to_deduct = 0
                    else:
                        qty_to_deduct -= batch.quantity_available
                        batch.quantity_available = 0
                        batch.save()
                        
        return JsonResponse({'status': 'success', 'message': 'Bill Generated Successfully!'})
        
    return render(request, 'erp/pos_terminal.html', {
        'products': Product.objects.filter(is_active=True), 
        'categories': Category.objects.all()
    })

@login_required(login_url='login')
def sales_bills(request):
    if not request.headers.get('HX-Request') and request.method == 'GET':
        return redirect('pos_terminal')
        
    return render(request, 'erp/sales_bills.html', {
        'orders': Order.objects.all().order_by('-created_at')
    })

@login_required(login_url='login')
def sales_return(request):
    if not request.headers.get('HX-Request') and request.method == 'GET':
        return redirect('erp_dashboard') if request.user.is_superuser else redirect('pos_terminal')
        
    success_msg = None
    error_msg = None
    
    if request.method == 'POST':
        product_id = request.POST.get('product')
        quantity = int(request.POST.get('quantity', 0))
        refund_amount = request.POST.get('refund_amount', 0)

        if quantity > 0:
            try:
                with transaction.atomic():
                    product = Product.objects.get(id=product_id)
                    batch, created = ProductBatch.objects.get_or_create(
                        product=product, 
                        batch_number="RETURNED-STOCK",
                        defaults={'quantity_received': quantity, 'quantity_available': quantity, 'purchase_price': 0}
                    )
                    if not created:
                        batch.quantity_available += quantity
                        batch.quantity_received += quantity
                        batch.save()
                        
                    product.stock_quantity += quantity
                    product.save()
                    
                    success_msg = f"Return Successful! Added {quantity} x {product.name} back to stock. Refund Initiated: ₹{refund_amount}"
            except Exception as e:
                error_msg = f"Error processing return: {e}"
        else:
            error_msg = "Return quantity must be greater than zero!"

    return render(request, 'erp/sales_return.html', {
        'products': Product.objects.filter(is_active=True), 
        'warehouses': Warehouse.objects.all(),
        'success_msg': success_msg, 
        'error_msg': error_msg
    })


# ==========================================
# 📊 BACK TO ADMIN ONLY MODULES
# ==========================================
@login_required(login_url='login')
@admin_only
def user_management(request):
    if not request.headers.get('HX-Request') and request.method == 'GET':
        return redirect('erp_dashboard')
        
    success_msg = None
    error_msg = None
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email', '')
        password = request.POST.get('password')
        role = request.POST.get('role')
        
        if User.objects.filter(username=username).exists():
            error_msg = f"Bro, username '{username}' already exists!"
        else:
            try:
                is_super = True if role == 'admin' else False
                User.objects.create(
                    username=username, 
                    email=email, 
                    password=make_password(password),
                    is_staff=True, 
                    is_superuser=is_super,
                    role=role.title()
                )
                success_msg = f"New user '{username}' created successfully."
            except Exception as e:
                error_msg = f"Error creating user: {e}"

    return render(request, 'erp/user_management.html', {
        'users': User.objects.all().order_by('-date_joined'), 
        'success_msg': success_msg, 
        'error_msg': error_msg
    })

@login_required(login_url='login')
@admin_only
def delete_user(request, id):
    if request.method == 'POST':
        user_to_delete = get_object_or_404(User, id=id)
        if user_to_delete.id != request.user.id:
            user_to_delete.delete()
    return redirect('user_management')

@login_required(login_url='login')
@admin_only
def reports_analytics(request):
    if not request.headers.get('HX-Request') and request.method == 'GET':
        return redirect('erp_dashboard')
        
    chart_labels = []
    chart_data = []
    today = timezone.now().date()
    
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        chart_labels.append(day.strftime('%a')) 
        daily_total = Order.objects.filter(created_at__date=day).aggregate(Sum('grand_total'))['grand_total__sum'] or 0
        chart_data.append(float(daily_total))
    
    context = {
        'total_revenue': Order.objects.aggregate(Sum('grand_total'))['grand_total__sum'] or 0,
        'total_orders': Order.objects.count(),
        'total_products': Product.objects.count(),
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }
    return render(request, 'erp/reports_analytics.html', context)

@login_required(login_url='login')
@admin_only
def system_settings(request):
    if not request.headers.get('HX-Request') and request.method == 'GET':
        return redirect('erp_dashboard')
        
    success_msg = None
    if request.method == 'POST':
        success_msg = "System configurations saved successfully."

    return render(request, 'erp/settings.html', {
        'success_msg': success_msg, 
        'app_version': 'v1.5.0', 
        'database_type': 'SQLite3 (Development)', 
        'system_status': 'Operational'
    })

@login_required(login_url='login')
@admin_only
def stock_take(request):
    if not request.headers.get('HX-Request') and request.method == 'GET':
        return redirect('erp_dashboard')

    success_msg = None
    error_msg = None
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                product_id = request.POST.get('product')
                physical_qty = int(request.POST.get('physical_qty', 0))
                
                product = Product.objects.get(id=product_id)
                system_qty = product.stock_quantity
                
                difference = physical_qty - system_qty

                if difference != 0:
                    audit_batch, created = ProductBatch.objects.get_or_create(
                        product_id=product_id, 
                        batch_number="AUDIT-ADJUST",
                        defaults={'quantity_received': difference, 'quantity_available': difference, 'purchase_price': 0}
                    )
                    if not created:
                        audit_batch.quantity_available += difference
                        audit_batch.quantity_received += difference
                        audit_batch.save()
                        
                    product.stock_quantity = physical_qty
                    product.save()
                    
                    status = "Surplus" if difference > 0 else "Shortage"
                    success_msg = f"Audit complete! {status} of {abs(difference)} units adjusted."
                else:
                    success_msg = "Perfect match! No adjustments needed."
        except Exception as e:
            error_msg = f"Error updating stock take: {e}"

    inventory = []
    for p in Product.objects.filter(is_active=True):
        inventory.append({'product': p, 'system_qty': p.stock_quantity})
        
    return render(request, 'erp/stock_take.html', {
        'products': Product.objects.filter(is_active=True), 
        'warehouses': Warehouse.objects.all(),
        'inventory': inventory, 
        'success_msg': success_msg, 
        'error_msg': error_msg
    })

@login_required(login_url='login')
@admin_only
def delivery_schedule(request):
    if not request.headers.get('HX-Request') and request.method == 'GET':
        return redirect('erp_dashboard')
        
    schedules = DeliverySchedule.objects.select_related('supplier').all().order_by('expected_date')
    
    today = timezone.now().date()
    end_of_week = today + timedelta(days=7)
    
    expected_this_week = DeliverySchedule.objects.filter(
        expected_date__range=[today, end_of_week]
    ).count()
    
    pending_confirmation = DeliverySchedule.objects.filter(status='Pending').count()
    
    context = {
        'schedules': schedules,
        'expected_this_week': expected_this_week,
        'pending_confirmation': pending_confirmation,
        'warehouse_capacity': "72%" 
    }
    return render(request, 'erp/delivery_schedule.html', context)

@login_required(login_url='login')
@admin_only
def mark_delivery_arrived(request, id):
    if request.method == 'POST':
        delivery = get_object_or_404(DeliverySchedule, id=id)
        delivery.status = 'Arrived'
        delivery.save()
    return redirect('delivery_schedule')

@login_required(login_url='login')
@admin_only
def export_report(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="GrandMart_Sales_Report.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Invoice ID', 'Date & Time', 'Total Amount (Rs)'])
    
    orders = Order.objects.all().order_by('-created_at')
    for order in orders:
        formatted_id = order.invoice_number
        formatted_date = order.created_at.strftime("%Y-%m-%d %H:%M")
        writer.writerow([formatted_id, formatted_date, order.grand_total])
        
    return response


# ==========================================
# 🗑️ DELETE & EDIT FUNCTIONS (Fixed Clone Bug)
# ==========================================
@login_required(login_url='login')
@admin_only
def delete_category(request, id):
    if request.method == 'POST':
        Category.objects.filter(id=id).delete()
    return redirect('categories_units')

@login_required(login_url='login')
@admin_only
def delete_unit(request, id):
    if request.method == 'POST':
        Unit.objects.filter(id=id).delete()
    return redirect('categories_units')

@login_required(login_url='login')
@admin_only
def delete_product(request, id):
    if request.method == 'POST':
        get_object_or_404(Product, id=id).delete()
        
    return render(request, 'erp/store_master.html', {
        'products': Product.objects.all().order_by('-id'), 
        'categories': Category.objects.all(), 
        'units': Unit.objects.all()
    })

@login_required(login_url='login')
def edit_product(request, id):
    product = get_object_or_404(Product, id=id)
    if request.method == 'POST':
        product.name = request.POST.get('name')
        
        cat_id = request.POST.get('category')
        if cat_id:
            product.category = Category.objects.get(id=cat_id)
            
        unit_id = request.POST.get('unit')
        if unit_id:
            product.unit = Unit.objects.get(id=unit_id)
            
        product.mrp_price = request.POST.get('mrp_price', 0)
        product.selling_price = request.POST.get('selling_price', 0)
        
        barcode = request.POST.get('barcode')
        product.barcode = barcode if barcode and barcode.strip() else None
        
        product.pack_size = request.POST.get('pack_size', '1 Pc') 
        
        # 🌟 IMAGE & URL LOGIC ADDED HERE 🌟
        if request.FILES.get('image'):
            product.image = request.FILES.get('image')
        if request.POST.get('image_url'):
            product.image_url = request.POST.get('image_url')
            
        product.save()
        
        return render(request, 'erp/store_master.html', {
            'products': Product.objects.all().order_by('-id'), 
            'categories': Category.objects.all(), 
            'units': Unit.objects.all()
        })
        
    categories = Category.objects.all()
    units = Unit.objects.all()
    all_products = Product.objects.filter(is_active=True).order_by('name')
    
    return render(request, 'erp/edit_product.html', {
        'product': product, 
        'categories': categories, 
        'units': units,
        'all_products': all_products
    })


# ==========================================
# 🔍 SEARCH & BULK UPLOAD FUNCTIONS
# ==========================================
@login_required(login_url='login')
def global_search(request):
    query = request.GET.get('q', '').strip()
    
    if not query:
        return HttpResponse("") 
        
    products = Product.objects.filter(
        Q(name__icontains=query) | Q(barcode__icontains=query)
    ).select_related('category')[:5]
    
    order_query = query.upper().replace('INV-', '').replace('INV', '').strip()
    orders = []
    if order_query.isdigit():
        orders = Order.objects.filter(invoice_number__icontains=order_query).order_by('-created_at')[:3]
        
    return render(request, 'erp/search_results.html', {
        'products': products,
        'orders': orders,
        'query': query
    })

# --- SMART BULK PASTE (Fixed Clone Bug) ---
@login_required(login_url='login')
def smart_bulk_paste(request):
    if request.method == 'POST':
        bulk_text = request.POST.get('bulk_data', '')
        lines = bulk_text.strip().split('\n')
        
        for line in lines:
            if not line.strip():
                continue 
                
            cols = line.split('\t') 
            if len(cols) >= 4:
                name = cols[0].strip()
                cat_name = cols[1].strip()
                
                if len(cols) >= 5:
                    mrp_str = cols[2].strip()
                    price_str = cols[3].strip()
                    size = cols[4].strip()
                else:
                    mrp_str = cols[2].strip()
                    price_str = cols[2].strip()
                    size = cols[3].strip()
                
                cat, created = Category.objects.get_or_create(name=cat_name)
                
                try:
                    mrp = float(mrp_str.replace(',', ''))
                    selling = float(price_str.replace(',', ''))
                except ValueError:
                    mrp, selling = 0.00, 0.00
                
                Product.objects.create(
                    name=name,
                    category=cat,
                    mrp_price=mrp,
                    selling_price=selling,
                    pack_size=size
                )
        
        return render(request, 'erp/store_master.html', {
            'products': Product.objects.all().order_by('-id'), 
            'categories': Category.objects.all(), 
            'units': Unit.objects.all()
        })
    
# ==========================================
# 🌐 E-COMMERCE STOREFRONT (Customer Side)
# ==========================================
def store_home(request):
    categories = Category.objects.filter(is_active=True)
    products = Product.objects.filter(is_active=True).order_by('-id')
    
    # Category Filter Logic
    cat_id = request.GET.get('category')
    search_query = request.GET.get('search')
    
    if cat_id:
        products = products.filter(category_id=cat_id)
        
    if search_query:
        products = products.filter(name__icontains=search_query)
        
    return render(request, 'store/home.html', {
        'categories': categories,
        'products': products,
        'active_category': int(cat_id) if cat_id and cat_id.isdigit() else None,
        'search_query': search_query
    })

# --- E-COMMERCE CHECKOUT ---
@transaction.atomic
def checkout(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        cart = data.get('cart', {})
        customer = data.get('customer', {})
        
        if not cart:
            return JsonResponse({'status': 'error', 'message': 'Cart is empty!'})
            
        total_amount = sum(item['price'] * item['qty'] for item in cart.values())
        
        # 1. Create Web Order
        order = Order.objects.create(
            order_type='WEB',
            customer_name=customer.get('name', 'Web Customer'),
            customer_phone=customer.get('phone', ''),
            shipping_address=customer.get('address', ''),
            payment_method=customer.get('payment_method', 'COD'),
            status='Pending', # New web orders are pending
            grand_total=total_amount,
            invoice_number=f"WEB-{timezone.now().timestamp()}"
        )
        order.invoice_number = f"WEB-{order.id:06d}"
        order.save()
        
        # 2. Deduct Live Stock & Batches
        for p_id, item in cart.items():
            qty_to_deduct = item['qty']
            product = Product.objects.get(id=p_id)
            
            if product.stock_quantity < qty_to_deduct:
                return JsonResponse({'status': 'error', 'message': f'Oops! {product.name} just went out of stock.'})
                
            product.stock_quantity -= qty_to_deduct
            product.save()
            
            batches = ProductBatch.objects.filter(product_id=p_id, quantity_available__gt=0).order_by('id')
            for batch in batches:
                if qty_to_deduct <= 0:
                    break
                if batch.quantity_available >= qty_to_deduct:
                    batch.quantity_available -= qty_to_deduct
                    batch.save()
                    qty_to_deduct = 0
                else:
                    qty_to_deduct -= batch.quantity_available
                    batch.quantity_available = 0
                    batch.save()
                    
        return JsonResponse({
            'status': 'success', 
            'message': 'Order Placed Successfully!', 
            'order_id': order.invoice_number
        })
        
    return render(request, 'store/checkout.html')

# ==========================================
# 📦 WEB ORDER MANAGEMENT (ERP SIDE)
# ==========================================
@login_required(login_url='login')
@admin_only
def web_orders(request):
    if not request.headers.get('HX-Request') and request.method == 'GET':
        pass # Add logic if needed, but normally allow GET
        
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        new_status = request.POST.get('status')
        
        if order_id and new_status:
            order = get_object_or_404(Order, id=order_id)
            order.status = new_status
            order.save()
            # In a real app, you might send an SMS/Email to customer here
            
        return redirect('web_orders')

    # Fetch only WEB orders, newest first
    orders = Order.objects.filter(order_type='WEB').order_by('-created_at')
    
    # Calculate some quick stats for the top cards
    pending_count = orders.filter(status='Pending').count()
    packing_count = orders.filter(status='Packing').count()
    delivery_count = orders.filter(status='Out for Delivery').count()
    
    return render(request, 'erp/web_orders.html', {
        'orders': orders,
        'pending_count': pending_count,
        'packing_count': packing_count,
        'delivery_count': delivery_count
    })

# ==========================================
# 🖨️ INVOICE & BILL PRINTING
# ==========================================
@login_required(login_url='login')
@xframe_options_sameorigin  # 🌟 இத புதுசா ஆட் பண்ணுங்க 🌟
def print_invoice(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    items = OrderItem.objects.filter(order=order)
    store = StoreSettings.objects.first()
    
    return render(request, 'erp/invoice.html', {
        'order': order,
        'items': items,
        'store': store
    })