from rest_framework import serializers

from .models import Conta, Proposta


class ContaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conta
        fields = [
            "id",
            "nome",
            "documento",
            "email",
            "telefone",
            "status",
            "data_criacao",
        ]
        read_only_fields = ["id", "data_criacao"]


class PropostaSerializer(serializers.ModelSerializer):
    conta = serializers.PrimaryKeyRelatedField(queryset=Conta.objects.all())

    class Meta:
        model = Proposta
        fields = [
            "id",
            "conta",
            "valor_total",
            "condicao_pagamento",
            "status",
            "data_validade",
        ]
        read_only_fields = ["id"]
