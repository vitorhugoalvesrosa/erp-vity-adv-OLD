from rest_framework import serializers

from crm.models import Conta, Proposta

from .models import ContaReceber, Pagamento, PedidoVenda


class PedidoVendaSerializer(serializers.ModelSerializer):
    proposta = serializers.PrimaryKeyRelatedField(queryset=Proposta.objects.all())

    class Meta:
        model = PedidoVenda
        fields = [
            "id",
            "proposta",
            "valor_final",
            "data_faturamento",
        ]
        read_only_fields = ["id"]


class ContaReceberSerializer(serializers.ModelSerializer):
    conta = serializers.PrimaryKeyRelatedField(queryset=Conta.objects.all())
    pedido_venda = serializers.PrimaryKeyRelatedField(queryset=PedidoVenda.objects.all())

    class Meta:
        model = ContaReceber
        fields = [
            "id",
            "conta",
            "pedido_venda",
            "valor_parcela",
            "data_vencimento",
            "status_pagamento",
        ]
        read_only_fields = ["id"]


class PagamentoSerializer(serializers.ModelSerializer):
    conta_receber = serializers.PrimaryKeyRelatedField(queryset=ContaReceber.objects.all())

    class Meta:
        model = Pagamento
        fields = [
            "id",
            "conta_receber",
            "valor",
            "data_pagamento",
            "metodo_pagamento",
        ]
        read_only_fields = ["id"]
