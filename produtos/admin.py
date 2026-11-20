from django.contrib import admin

from .models import Produto


@admin.register(Produto)
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
