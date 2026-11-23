from rest_framework import serializers

from .models import Movimentacao, Prazo, Processo, Publicacao, Tarefa


class ProcessoSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    responsavel_nome = serializers.CharField(
        source="responsavel.get_full_name",
        read_only=True,
    )
    area_display = serializers.CharField(source="get_area_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Processo
        fields = (
            "id",
            "numero_cnj",
            "titulo",
            "cliente",
            "cliente_nome",
            "parte_contraria",
            "tribunal",
            "vara",
            "area",
            "area_display",
            "status",
            "status_display",
            "responsavel",
            "responsavel_nome",
            "valor_causa",
            "observacoes",
            "criado_em",
            "atualizado_em",
        )
        read_only_fields = ("id", "criado_em", "atualizado_em")

    def validate_numero_cnj(self, value):
        compact = "".join(value.split())
        if len(compact) < 20:
            raise serializers.ValidationError(
                "Informe um número CNJ válido com pelo menos 20 caracteres."
            )
        return compact


class MovimentacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movimentacao
        fields = "__all__"
        read_only_fields = ("id", "criada_em")


class PrazoSerializer(serializers.ModelSerializer):
    processo_numero = serializers.CharField(
        source="processo.numero_cnj",
        read_only=True,
    )
    responsavel_nome = serializers.CharField(
        source="responsavel.get_full_name",
        read_only=True,
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Prazo
        fields = "__all__"
        read_only_fields = ("id", "criado_em")


class TarefaSerializer(serializers.ModelSerializer):
    responsavel_nome = serializers.CharField(
        source="responsavel.get_full_name",
        read_only=True,
    )
    prioridade_display = serializers.CharField(
        source="get_prioridade_display",
        read_only=True,
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Tarefa
        fields = "__all__"
        read_only_fields = ("id", "criada_em")


class PublicacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publicacao
        fields = "__all__"
        read_only_fields = ("id", "capturada_em")
