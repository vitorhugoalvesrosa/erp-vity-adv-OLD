from django.db import models


class Conta(models.Model):
    class Status(models.TextChoices):
        LEAD = "lead", "Lead"
        NEGOCIACAO = "negociacao", "Negociação"
        CLIENTE = "cliente", "Cliente"

    nome = models.CharField(max_length=255)
    documento = models.CharField(max_length=20, unique=True, help_text="CNPJ ou CPF")
    email = models.EmailField(blank=True, default="")
    telefone = models.CharField(max_length=30, blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.LEAD,
    )
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data_criacao"]
        verbose_name = "Conta"
        verbose_name_plural = "Contas"

    def __str__(self):
        return self.nome


class Proposta(models.Model):
    class CondicaoPagamento(models.TextChoices):
        A_VISTA = "a_vista", "À vista"
        TRINTA_DIAS = "30_dias", "30 dias"
        TRINTA_SIXENTA_NOVENTA = "30_60_90", "30/60/90"

    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        ENVIADA = "enviada", "Enviada"
        GANHA = "ganha", "Ganha"
        PERDIDA = "perdida", "Perdida"

    conta = models.ForeignKey(
        Conta,
        on_delete=models.CASCADE,
        related_name="propostas",
    )
    valor_total = models.DecimalField(max_digits=12, decimal_places=2)
    condicao_pagamento = models.CharField(
        max_length=20,
        choices=CondicaoPagamento.choices,
        default=CondicaoPagamento.A_VISTA,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RASCUNHO,
    )
    data_validade = models.DateField()

    class Meta:
        ordering = ["-data_validade"]
        verbose_name = "Proposta"
        verbose_name_plural = "Propostas"

    def __str__(self):
        return f"Proposta {self.pk} - {self.conta.nome}"
