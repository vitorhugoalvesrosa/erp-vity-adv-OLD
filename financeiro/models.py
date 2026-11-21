from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

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


class Contrato(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        AGUARDANDO_ASSINATURA = "aguardando_assinatura", "Aguardando assinatura"
        ATIVO = "ativo", "Ativo"
        CONCLUIDO = "concluido", "Concluído"
        RESCINDIDO = "rescindido", "Rescindido"

    pedido_venda = models.OneToOneField(
        PedidoVenda,
        on_delete=models.PROTECT,
        related_name="contrato",
        verbose_name="Pedido de venda",
    )
    contract_date = models.DateField("Data do contrato", default=timezone.localdate)
    start_date = models.DateField("Início da vigência", default=timezone.localdate)
    end_date = models.DateField("Fim da vigência", blank=True, null=True)
    service_location = models.CharField("Local da prestação", max_length=255, blank=True)
    service_description = models.TextField("Objeto e escopo dos serviços")
    payment_terms = models.TextField("Condições de pagamento")
    client_representative = models.CharField(
        "Representante do contratante", max_length=255, blank=True
    )
    termination_notice_days = models.PositiveSmallIntegerField(
        "Aviso prévio para rescisão (dias)", default=30
    )
    additional_clauses = models.TextField("Condições adicionais", blank=True)
    status = models.CharField(
        "Status",
        max_length=24,
        choices=Status.choices,
        default=Status.RASCUNHO,
    )
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["-contract_date", "-id"]
        verbose_name = "Contrato"
        verbose_name_plural = "Contratos"

    def clean(self):
        super().clean()
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "O fim da vigência deve ser posterior ao início."})

    @property
    def number(self):
        return f"CTR-{self.contract_date.year}-{self.pk:06d}" if self.pk else "Novo contrato"

    @property
    def cliente(self):
        return self.pedido_venda.proposta.conta.nome

    def __str__(self):
        return f"{self.number} - {self.pedido_venda.proposta.conta.nome}"


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
