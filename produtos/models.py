from django.db import models


class Produto(models.Model):
    class CategoriaEstetica(models.TextChoices):
        FACIAL = "facial", "Facial"
        CORPORAL = "corporal", "Corporal"
        CAPILAR = "capilar", "Capilar"
        DE_PILACAO = "depilacao", "Depilação"
        UNHAS = "unhas", "Manicure e pedicure"
        SOBRANCELHAS = "sobrancelhas", "Sobrancelhas"
        MAQUIAGEM = "maquiagem", "Maquiagem"
        OUTROS = "outros", "Outros"

    nome = models.CharField(max_length=255)
    descricao = models.TextField(blank=True, default="")
    sku = models.CharField(max_length=100, unique=True)
    preco = models.DecimalField(max_digits=12, decimal_places=2)
    eh_servico = models.BooleanField(
        default=False,
        verbose_name="É um serviço (não controla estoque)",
    )
    categoria_estetica = models.CharField(
        max_length=20,
        choices=CategoriaEstetica.choices,
        blank=True,
        default="",
        verbose_name="Categoria estética",
    )
    duracao_minutos = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Duração estimada (minutos)",
    )
    quantidade_estoque = models.IntegerField(default=0)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data_criacao"]
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if self.eh_servico:
            self.quantidade_estoque = 0
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = {
                    *kwargs["update_fields"],
                    "quantidade_estoque",
                }
        super().save(*args, **kwargs)
