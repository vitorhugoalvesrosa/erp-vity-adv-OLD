from rest_framework import viewsets

from .models import ContaReceber, Pagamento, PedidoVenda
from .serializers import ContaReceberSerializer, PagamentoSerializer, PedidoVendaSerializer


class PedidoVendaViewSet(viewsets.ModelViewSet):
    queryset = PedidoVenda.objects.select_related("proposta", "proposta__conta").all().order_by("-data_faturamento")
    serializer_class = PedidoVendaSerializer


class ContaReceberViewSet(viewsets.ModelViewSet):
    queryset = ContaReceber.objects.select_related("conta", "pedido_venda").all().order_by("data_vencimento")
    serializer_class = ContaReceberSerializer


class PagamentoViewSet(viewsets.ModelViewSet):
    queryset = Pagamento.objects.select_related("conta_receber", "conta_receber__conta").all().order_by("-data_pagamento")
    serializer_class = PagamentoSerializer
