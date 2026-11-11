from django.db import models

from crm.models import Conta, Proposta


class PedidoVenda(models.Model):
    proposta = models.OneToOneField(
        Proposta,
        on_delete=models.CASCADE,
        related_name="pedido_venda",
    )
    valor_final = models.DecimalField(max_digits=12, decimal_places=2)
    data_faturamento = models.DateField()

    class Meta:
        ordering = ["-data_faturamento"]
        verbose_name = "Pedido de Venda"
        verbose_name_plural = "Pedidos de Venda"

    def __str__(self):
        return f"Pedido {self.pk} - {self.proposta.conta.nome}"


class ContaReceber(models.Model):
    class StatusPagamento(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        PAGO = "pago", "Pago"
        ATRASADO = "atrasado", "Atrasado"

    conta = models.ForeignKey(
        Conta,
        on_delete=models.CASCADE,
        related_name="contas_receber",
    )
    pedido_venda = models.ForeignKey(
        PedidoVenda,
        on_delete=models.CASCADE,
        related_name="contas_receber",
    )
    valor_parcela = models.DecimalField(max_digits=12, decimal_places=2)
    data_vencimento = models.DateField()
    status_pagamento = models.CharField(
        max_length=20,
        choices=StatusPagamento.choices,
        default=StatusPagamento.PENDENTE,
    )

    class Meta:
        ordering = ["data_vencimento"]
        verbose_name = "Conta a Receber"
        verbose_name_plural = "Contas a Receber"

    def __str__(self):
        return f"{self.conta.nome} - {self.valor_parcela}"


class Pagamento(models.Model):
    class MetodoPagamento(models.TextChoices):
        PIX = "pix", "Pix"
        BOLETO = "boleto", "Boleto"
        CARTAO = "cartao", "Cartão"
        TRANSFERENCIA = "transferencia", "Transferência"

    conta_receber = models.ForeignKey(
        ContaReceber,
        on_delete=models.CASCADE,
        related_name="pagamentos",
    )
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    data_pagamento = models.DateField()
    metodo_pagamento = models.CharField(
        max_length=20,
        choices=MetodoPagamento.choices,
        default=MetodoPagamento.PIX,
    )

    class Meta:
        ordering = ["-data_pagamento"]
        verbose_name = "Pagamento"
        verbose_name_plural = "Pagamentos"

    def __str__(self):
        return f"Pagamento {self.pk} - {self.valor}"
