from rest_framework import serializers

from .models import Produto


class ProdutoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Produto
        fields = [
            "id",
            "nome",
            "descricao",
            "sku",
            "preco",
            "eh_servico",
            "categoria_estetica",
            "duracao_minutos",
            "quantidade_estoque",
            "ativo",
            "data_criacao",
        ]
        read_only_fields = ["id", "data_criacao"]
