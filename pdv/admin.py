from django.contrib import admin

from core.admin_site import erp_admin_site

from .models import CashMovement, CashRegister, Sale, SaleItem, SaleTender


@admin.register(CashRegister, site=erp_admin_site)
class CashRegisterAdmin(admin.ModelAdmin):
    list_display = (
        "cashier",
        "opening_amount",
        "opened_at",
        "closed_at",
        "counted_amount",
        "expected_amount",
    )
    list_filter = ("closed_at", "opened_at")
    readonly_fields = tuple(field.name for field in CashRegister._meta.fields)

    def has_add_permission(self, request):
        return False


@admin.register(CashMovement, site=erp_admin_site)
class CashMovementAdmin(admin.ModelAdmin):
    list_display = ("register", "direction", "kind", "amount", "created_by", "created_at")
    list_filter = ("direction", "kind", "created_at")
    readonly_fields = tuple(field.name for field in CashMovement._meta.fields)

    def has_add_permission(self, request):
        return False


@admin.register(Sale, site=erp_admin_site)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "cashier",
        "customer",
        "status",
        "fiscal_status",
        "total",
        "created_at",
        "completed_at",
    )
    list_filter = ("status", "fiscal_status", "created_at")
    readonly_fields = tuple(field.name for field in Sale._meta.fields)

    def has_add_permission(self, request):
        return False


@admin.register(SaleItem, site=erp_admin_site)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ("sale", "product_name", "sku", "quantity", "unit_price", "line_total")
    readonly_fields = tuple(field.name for field in SaleItem._meta.fields)

    def has_add_permission(self, request):
        return False


@admin.register(SaleTender, site=erp_admin_site)
class SaleTenderAdmin(admin.ModelAdmin):
    list_display = ("sale", "method", "amount", "reference")
    readonly_fields = tuple(field.name for field in SaleTender._meta.fields)

    def has_add_permission(self, request):
        return False
