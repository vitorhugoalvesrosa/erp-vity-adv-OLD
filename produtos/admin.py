from django.contrib import admin

from core.admin_site import erp_admin_site
from .models import Produto


@admin.register(Produto, site=erp_admin_site)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "sku",
        "preco",
        "quantidade_estoque",
        "ativo",
        "data_criacao",
    )
    list_filter = ("ativo", "data_criacao")
    search_fields = ("nome", "sku")
