from django.urls import path
from . import views
import csv
from django.http import HttpResponse, JsonResponse

urlpatterns = [
    # --- CUSTOMER STOREFRONT ---
    path('', views.store_home, name='store_home'),
    path('checkout/', views.checkout, name='checkout'),
    
    # --- AUTHENTICATION (🌟 FIXED CLASH 🌟) ---
    path('login/', views.user_login, name='login'), 
    path('logout/', views.user_logout, name='logout'),

    # --- DASHBOARD ---
    path('erp/dashboard/', views.erp_dashboard, name='erp_dashboard'),
    path('erp/export-report/', views.export_report, name='export_report'),
    
    # --- GLOBAL SEARCH ---
    path('erp/global-search/', views.global_search, name='global_search'),

    # --- PRINT INVOICE ---
    path('invoice/<int:order_id>/', views.print_invoice, name='print_invoice'),

    # --- MASTER CONFIGURATION ---
    path('erp/general-master/', views.general_master, name='general_master'),
    path('erp/store-master/', views.store_master, name='store_master'),
    path('erp/categories-units/', views.categories_units, name='categories_units'),
    path('erp/store-master/bulk-paste/', views.smart_bulk_paste, name='smart_bulk_paste'),
    
    # --- INVENTORY SETUP ---
    path('erp/stock-balance/', views.stock_balance, name='stock_balance'),
    path('erp/stock-take/', views.stock_take, name='stock_take'),
    path('erp/received-goods/', views.received_goods, name='received_goods'),
    path('erp/transfer-goods/', views.transfer_goods, name='transfer_goods'),
    path('erp/delivery-schedule/', views.delivery_schedule, name='delivery_schedule'),
    
    # --- DELIVERY SCHEDULE ACTION ---
    path('erp/delivery-schedule/arrived/<int:id>/', views.mark_delivery_arrived, name='mark_delivery_arrived'),
    
    # --- SALES & BILLING ---
    path('erp/pos-terminal/', views.pos_terminal, name='pos_terminal'),
    path('web-orders/', views.web_orders, name='web_orders'),
    path('erp/sales-bills/', views.sales_bills, name='sales_bills'),
    path('erp/sales-return/', views.sales_return, name='sales_return'),

    # --- ADMINISTRATION ---
    path('erp/user-management/', views.user_management, name='user_management'),
    path('erp/reports-analytics/', views.reports_analytics, name='reports_analytics'),
    path('erp/settings/', views.system_settings, name='settings'),

    # --- DELETE & EDIT FUNCTIONS ---
    path('erp/delete-category/<int:id>/', views.delete_category, name='delete_category'),
    path('erp/delete-unit/<int:id>/', views.delete_unit, name='delete_unit'),
    path('erp/delete-product/<int:id>/', views.delete_product, name='delete_product'),
    path('erp/edit-product/<int:id>/', views.edit_product, name='edit_product'),
    
    # --- DELETE STAFF ACCOUNT ---
    path('erp/delete-user/<int:id>/', views.delete_user, name='delete_user'),
]