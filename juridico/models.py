from django.conf import settings
from django.db import models

from crm.models import Conta


class Processo(models.Model):
    class Area(models.TextChoices):
        CIVEL = "civel", "Cível"
        TRABALHISTA = "trabalhista", "Trabalhista"
        TRIBUTARIO = "tributario", "Tributário"
        EMPRESARIAL = "empresarial", "Empresarial"
        CRIMINAL = "criminal", "Criminal"
        FAMILIA = "familia", "Família"
        OUTRA = "outra", "Outra"

    class Status(models.TextChoices):
        ATIVO = "ativo", "Ativo"
        SUSPENSO = "suspenso", "Suspenso"
        ARQUIVADO = "arquivado", "Arquivado"
        ENCERRADO = "encerrado", "Encerrado"

    numero_cnj = models.CharField("Número CNJ", max_length=25, unique=True)
    titulo = models.CharField("Título", max_length=255)
    cliente = models.ForeignKey(
        Conta,
        on_delete=models.PROTECT,
        related_name="processos",
        verbose_name="Cliente",
    )
    parte_contraria = models.CharField("Parte contrária", max_length=255, blank=True)
    tribunal = models.CharField("Tribunal", max_length=100)
    vara = models.CharField("Vara/comarca", max_length=120, blank=True)
    area = models.CharField(max_length=20, choices=Area.choices, default=Area.CIVEL)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ATIVO,
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="processos_responsavel",
        verbose_name="Responsável",
    )
    valor_causa = models.DecimalField(
        "Valor da causa",
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    observacoes = models.TextField("Observações", blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-atualizado_em"]
        verbose_name = "Processo"
        verbose_name_plural = "Processos"

    def __str__(self):
        return f"{self.numero_cnj} - {self.titulo}"


class Movimentacao(models.Model):
    processo = models.ForeignKey(
        Processo,
        on_delete=models.CASCADE,
        related_name="movimentacoes",
    )
    data = models.DateField("Data")
    descricao = models.CharField("Descrição", max_length=500)
    origem = models.CharField(
        "Origem",
        max_length=30,
        default="manual",
    )
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data", "-criada_em"]
        verbose_name = "Movimentação"
        verbose_name_plural = "Movimentações"


class Prazo(models.Model):
    class Status(models.TextChoices):
        ABERTO = "aberto", "Aberto"
        CONCLUIDO = "concluido", "Concluído"
        PERDIDO = "perdido", "Perdido"

    processo = models.ForeignKey(
        Processo,
        on_delete=models.CASCADE,
        related_name="prazos",
    )
    titulo = models.CharField("Título", max_length=255)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="prazos_responsavel",
    )
    data_vencimento = models.DateField("Vencimento")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ABERTO)
    observacoes = models.TextField("Observações", blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["data_vencimento", "titulo"]
        verbose_name = "Prazo"
        verbose_name_plural = "Prazos"


class Tarefa(models.Model):
    class Prioridade(models.TextChoices):
        BAIXA = "baixa", "Baixa"
        MEDIA = "media", "Média"
        ALTA = "alta", "Alta"
        URGENTE = "urgente", "Urgente"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        EM_ANDAMENTO = "em_andamento", "Em andamento"
        CONCLUIDA = "concluida", "Concluída"
        CANCELADA = "cancelada", "Cancelada"

    processo = models.ForeignKey(
        Processo,
        on_delete=models.CASCADE,
        related_name="tarefas",
        null=True,
        blank=True,
    )
    titulo = models.CharField("Título", max_length=255)
    descricao = models.TextField("Descrição", blank=True)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tarefas_responsavel",
    )
    prioridade = models.CharField(
        max_length=20,
        choices=Prioridade.choices,
        default=Prioridade.MEDIA,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
    )
    vencimento = models.DateField("Vencimento", null=True, blank=True)
    concluida_em = models.DateTimeField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["status", "vencimento", "-prioridade"]
        verbose_name = "Tarefa"
        verbose_name_plural = "Tarefas"


class Publicacao(models.Model):
    processo = models.ForeignKey(
        Processo,
        on_delete=models.SET_NULL,
        related_name="publicacoes",
        null=True,
        blank=True,
    )
    monitoramento = models.CharField("CPF/CNPJ/OAB monitorado", max_length=30)
    tribunal = models.CharField("Tribunal", max_length=100)
    titulo = models.CharField("Título", max_length=255)
    conteudo = models.TextField("Conteúdo")
    publicada_em = models.DateField("Data da publicação")
    capturada_em = models.DateTimeField(auto_now_add=True)
    urgente = models.BooleanField("Urgente", default=False)
    processada = models.BooleanField("Processada", default=False)

    class Meta:
        ordering = ["-publicada_em", "-capturada_em"]
        verbose_name = "Publicação"
        verbose_name_plural = "Publicações"
