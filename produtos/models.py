from django.db import models


class Produto(models.Model):
    nome = models.CharField(max_length=255)
    descricao = models.TextField(blank=True, default="")
    sku = models.CharField(max_length=100, unique=True)
    preco = models.DecimalField(max_digits=12, decimal_places=2)
    quantidade_estoque = models.IntegerField(default=0)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data_criacao"]
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"

    def __str__(self):
        return self.nome
