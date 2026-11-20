from django.contrib import admin

from .models import ContaReceber, Pagamento, PedidoVenda


@admin.register(PedidoVenda)
class PedidoVendaAdmin(admin.ModelAdmin):
    list_display = ("id", "proposta", "valor_final", "data_faturamento")
    list_filter = ("data_faturamento",)


@admin.register(ContaReceber)
class ContaReceberAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conta",
        "pedido_venda",
        "valor_parcela",
        "data_vencimento",
        "status_pagamento",
    )
    list_filter = ("status_pagamento", "data_vencimento")
    search_fields = ("conta__nome",)


@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conta_receber",
        "valor",
        "data_pagamento",
        "metodo_pagamento",
    )
    list_filter = ("metodo_pagamento", "data_pagamento")
    search_fields = ("conta_receber__conta__nome",)
