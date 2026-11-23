from django.contrib import admin

from core.admin_site import erp_admin_site
from .models import Movimentacao, Prazo, Processo, Publicacao, Tarefa


class MovimentacaoInline(admin.TabularInline):
    model = Movimentacao
    extra = 0


class PrazoInline(admin.TabularInline):
    model = Prazo
    extra = 0


@admin.register(Processo, site=erp_admin_site)
class ProcessoAdmin(admin.ModelAdmin):
    list_display = (
        "numero_cnj",
        "titulo",
        "cliente",
        "area",
        "status",
        "responsavel",
        "atualizado_em",
    )
    list_filter = ("area", "status", "tribunal", "responsavel")
    search_fields = ("numero_cnj", "titulo", "parte_contraria", "cliente__nome")
    inlines = (MovimentacaoInline, PrazoInline)


@admin.register(Tarefa, site=erp_admin_site)
class TarefaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "processo", "responsavel", "prioridade", "vencimento", "status")
    list_filter = ("prioridade", "status", "responsavel")
    search_fields = ("titulo", "descricao", "processo__numero_cnj")


@admin.register(Publicacao, site=erp_admin_site)
class PublicacaoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "tribunal", "monitoramento", "publicada_em", "urgente", "processada")
    list_filter = ("urgente", "processada", "tribunal")
    search_fields = ("titulo", "conteudo", "monitoramento")
