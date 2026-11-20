from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from crm.models import Conta
from produtos.models import Produto


class CashRegister(models.Model):
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pdv_cash_registers",
    )
    opening_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    counted_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    expected_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-opened_at"]
        verbose_name = "Caixa do PDV"
        verbose_name_plural = "Caixas do PDV"
        permissions = [("close_cashregister", "Pode fechar caixa do PDV")]
        constraints = [
            models.UniqueConstraint(
                fields=("cashier",),
                condition=Q(closed_at__isnull=True),
                name="pdv_one_open_register_per_cashier",
            )
        ]

    @property
    def is_open(self):
        return self.closed_at is None

    def __str__(self):
        return f"Caixa de {self.cashier} · {self.opened_at:%d/%m/%Y %H:%M}"


class CashMovement(models.Model):
    class Direction(models.TextChoices):
        IN = "in", "Entrada"
        OUT = "out", "Saída"

    class Kind(models.TextChoices):
        SUPPLY = "supply", "Suprimento"
        WITHDRAWAL = "withdrawal", "Sangria"
        SALE = "sale", "Venda em dinheiro"
        REFUND = "refund", "Devolução em dinheiro"

    register = models.ForeignKey(
        CashRegister,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    direction = models.CharField(max_length=3, choices=Direction.choices)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    description = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pdv_cash_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Movimentação de caixa"
        verbose_name_plural = "Movimentações de caixa"

    def __str__(self):
        return f"{self.get_kind_display()} · R$ {self.amount}"


class Sale(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Em preparação"
        COMPLETED = "completed", "Concluída"
        CANCELLED = "cancelled", "Cancelada"

    register = models.ForeignKey(
        CashRegister,
        on_delete=models.PROTECT,
        related_name="sales",
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pdv_sales",
    )
    customer = models.ForeignKey(
        Conta,
        on_delete=models.PROTECT,
        related_name="pdv_sales",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Venda do PDV"
        verbose_name_plural = "Vendas do PDV"
        permissions = [("cancel_sale", "Pode cancelar venda concluída no PDV")]

    def __str__(self):
        return f"Venda #{self.pk} · {self.get_status_display()}"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Produto,
        on_delete=models.PROTECT,
        related_name="pdv_sale_items",
    )
    product_name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100)
    is_service = models.BooleanField()
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(0.001)],
    )
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Item da venda"
        verbose_name_plural = "Itens da venda"

    def __str__(self):
        return f"{self.quantity} × {self.product_name}"


class SaleTender(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Dinheiro"
        PIX = "pix", "Pix"
        DEBIT = "debit", "Cartão de débito"
        CREDIT = "credit", "Cartão de crédito"
        VOUCHER = "voucher", "Vale / voucher"
        TRANSFER = "transfer", "Transferência"

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="tenders")
    method = models.CharField(max_length=20, choices=Method.choices)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    reference = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Forma de pagamento da venda"
        verbose_name_plural = "Formas de pagamento da venda"

    def __str__(self):
        return f"{self.get_method_display()} · R$ {self.amount}"
