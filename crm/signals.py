from datetime import timedelta

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from crm.models import Conta, Proposta
from financeiro.models import ContaReceber, PedidoVenda


@receiver(pre_save, sender=Proposta)
def capture_previous_proposta_status(sender, instance, **kwargs):
    if instance.pk:
        previous_status = Proposta.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
        instance._previous_status = previous_status
    else:
        instance._previous_status = None


@receiver(post_save, sender=Proposta)
def proposta_to_pedido_venda(sender, instance, created, **kwargs):
    """Converte uma proposta vencedora em pedido e gera parcelas em ERP financeiro."""
    previous_status = getattr(instance, "_previous_status", None)

    if instance.status != Proposta.Status.GANHA or previous_status == Proposta.Status.GANHA:
        return

    try:
        with transaction.atomic():
            conta = instance.conta
            conta.status = Conta.Status.CLIENTE
            conta.save(update_fields=["status"])

            pedido, pedido_created = PedidoVenda.objects.get_or_create(
                proposta=instance,
                defaults={
                    "valor_final": instance.valor_total,
                    "data_faturamento": instance.data_validade,
                },
            )

            if not pedido_created:
                pedido.valor_final = instance.valor_total
                pedido.data_faturamento = instance.data_validade
                pedido.save(update_fields=["valor_final", "data_faturamento"])

            if instance.condicao_pagamento == Proposta.CondicaoPagamento.A_VISTA:
                parcelas = [
                    {
                        "valor": instance.valor_total,
                        "data": instance.data_validade,
                    }
                ]
            elif instance.condicao_pagamento == Proposta.CondicaoPagamento.TRINTA_DIAS:
                parcelas = [
                    {
                        "valor": instance.valor_total,
                        "data": instance.data_validade + timedelta(days=30),
                    }
                ]
            elif instance.condicao_pagamento == Proposta.CondicaoPagamento.TRINTA_SIXENTA_NOVENTA:
                parcela_base = instance.valor_total / 3
                parcelas = [
                    {"valor": round(parcela_base, 2), "data": instance.data_validade + timedelta(days=30)},
                    {"valor": round(parcela_base, 2), "data": instance.data_validade + timedelta(days=60)},
                    {"valor": round(instance.valor_total - (parcela_base * 2), 2), "data": instance.data_validade + timedelta(days=90)},
                ]
            else:
                parcelas = []

            for item in parcelas:
                valor_parcela = item["valor"]
                data_vencimento = item["data"]
                exists = ContaReceber.objects.filter(
                    conta=conta,
                    pedido_venda=pedido,
                    valor_parcela=valor_parcela,
                    data_vencimento=data_vencimento,
                ).exists()
                if exists:
                    continue
                ContaReceber.objects.create(
                    conta=conta,
                    pedido_venda=pedido,
                    valor_parcela=valor_parcela,
                    data_vencimento=data_vencimento,
                    status_pagamento=ContaReceber.StatusPagamento.PENDENTE,
                )
    except Exception:
        transaction.set_rollback(True)
        raise
