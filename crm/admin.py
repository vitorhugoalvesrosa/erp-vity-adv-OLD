from django.contrib import admin

from core.admin_site import erp_admin_site
from .models import Conta, Proposta


@admin.register(Conta, site=erp_admin_site)
class ContaAdmin(admin.ModelAdmin):
    list_display = ("nome", "documento", "email", "status", "data_criacao")
    list_filter = ("status", "data_criacao")
    search_fields = ("nome", "documento", "email")


@admin.register(Proposta, site=erp_admin_site)
class PropostaAdmin(admin.ModelAdmin):
    list_display = ("id", "conta", "valor_total", "status", "data_validade")
    list_filter = ("status", "condicao_pagamento", "data_validade")
    search_fields = ("conta__nome",)
