from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from produtos.models import Produto

from .models import CashMovement, CashRegister, Sale, SaleItem, SaleTender


CENT = Decimal("0.01")


class POSWorkflowError(Exception):
    pass


def _money(value):
    try:
        raw_amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise POSWorkflowError("Informe um valor monetário válido.") from exc
    if not raw_amount.is_finite():
        raise POSWorkflowError("Informe um valor monetário válido.")
    amount = raw_amount.quantize(CENT, rounding=ROUND_HALF_UP)
    if raw_amount != amount:
        raise POSWorkflowError("Valores monetários devem ter até duas casas decimais.")
    return amount


def _quantity(value):
    try:
        raw_quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise POSWorkflowError("Informe uma quantidade válida.") from exc
    if not raw_quantity.is_finite():
        raise POSWorkflowError("Informe uma quantidade válida.")
    quantity = raw_quantity.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    if raw_quantity != quantity:
        raise POSWorkflowError("A quantidade deve ter até três casas decimais.")
    return quantity


def open_register(user, opening_amount):
    amount = _money(opening_amount)
    if amount < 0:
        raise POSWorkflowError("O fundo de caixa não pode ser negativo.")
    try:
        with transaction.atomic():
            return CashRegister.objects.create(
                cashier=user,
                opening_amount=amount,
            )
    except IntegrityError as exc:
        raise POSWorkflowError("Você já possui um caixa aberto.") from exc


def record_cash_movement(register, user, direction, amount, description):
    amount = _money(amount)
    description = description.strip()
    if amount <= 0:
        raise POSWorkflowError("O valor da movimentação deve ser maior que zero.")
    if direction not in {CashMovement.Direction.IN, CashMovement.Direction.OUT}:
        raise POSWorkflowError("Tipo de movimentação inválido.")
    if not description:
        raise POSWorkflowError("Informe o motivo da movimentação.")
    kind = (
        CashMovement.Kind.SUPPLY
        if direction == CashMovement.Direction.IN
        else CashMovement.Kind.WITHDRAWAL
    )
    with transaction.atomic():
        register = CashRegister.objects.select_for_update().get(pk=register.pk)
        if not register.is_open:
            raise POSWorkflowError("O caixa está fechado.")
        if register.cashier_id != user.pk and not user.has_perm("pdv.change_cashregister"):
            raise POSWorkflowError("Você não pode movimentar o caixa de outro operador.")
        return CashMovement.objects.create(
            register=register,
            direction=direction,
            kind=kind,
            amount=amount,
            description=description,
            created_by=user,
        )


def expected_cash(register):
    totals = register.movements.aggregate(
        incoming=Sum("amount", filter=Q(direction=CashMovement.Direction.IN)),
        outgoing=Sum("amount", filter=Q(direction=CashMovement.Direction.OUT)),
    )
    incoming = totals["incoming"] or Decimal("0.00")
    outgoing = totals["outgoing"] or Decimal("0.00")
    return (register.opening_amount + incoming - outgoing).quantize(CENT)


def close_register(register, counted_amount):
    counted = _money(counted_amount)
    if counted < 0:
        raise POSWorkflowError("O valor contado não pode ser negativo.")
    with transaction.atomic():
        register = CashRegister.objects.select_for_update().get(pk=register.pk)
        if not register.is_open:
            raise POSWorkflowError("O caixa já está fechado.")
        if register.sales.filter(status=Sale.Status.DRAFT).exists():
            raise POSWorkflowError(
                "Cancele ou finalize os rascunhos antes de fechar o caixa."
            )
        register.expected_amount = expected_cash(register)
        register.counted_amount = counted
        register.closed_at = timezone.now()
        register.save(
            update_fields=("expected_amount", "counted_amount", "closed_at"),
        )
    return register


def create_draft_sale(register, cashier, lines, tenders, discount_amount, customer=None):
    if not register.is_open:
        raise POSWorkflowError("Abra o caixa antes de iniciar uma venda.")
    if register.cashier_id != cashier.pk:
        raise POSWorkflowError("Este caixa pertence a outro operador.")
    if not isinstance(lines, list) or not lines:
        raise POSWorkflowError("Adicione pelo menos um produto ou serviço.")
    if not isinstance(tenders, list):
        raise POSWorkflowError("Informe as formas de pagamento.")

    quantities = {}
    for line in lines:
        if not isinstance(line, dict):
            raise POSWorkflowError("Os itens da venda são inválidos.")
        sku = str(line.get("sku", "")).strip()
        if not sku:
            raise POSWorkflowError("Informe o SKU ou código de barras.")
        quantity = _quantity(line.get("quantity", "0"))
        if quantity <= 0:
            raise POSWorkflowError("A quantidade deve ser maior que zero.")
        quantities[sku] = quantities.get(sku, Decimal("0")) + quantity

    products = {
        product.sku: product
        for product in Produto.objects.filter(
            sku__in=quantities,
            ativo=True,
        )
    }
    if len(products) != len(quantities):
        missing = sorted(set(quantities) - set(products))
        raise POSWorkflowError(f"SKU não encontrado ou inativo: {', '.join(missing)}.")

    sale_lines = []
    subtotal = Decimal("0.00")
    for sku, quantity in quantities.items():
        product = products[sku]
        if not product.eh_servico:
            if quantity != quantity.to_integral_value():
                raise POSWorkflowError(
                    f"A quantidade de {product.nome} deve ser um número inteiro."
                )
            if quantity > product.quantidade_estoque:
                raise POSWorkflowError(
                    f"Estoque insuficiente para {product.nome}; disponível: "
                    f"{product.quantidade_estoque}."
                )
        line_total = (product.preco * quantity).quantize(CENT, rounding=ROUND_HALF_UP)
        subtotal += line_total
        sale_lines.append((product, quantity, line_total))

    discount = _money(discount_amount)
    if discount < 0 or discount > subtotal:
        raise POSWorkflowError("O desconto deve estar entre zero e o subtotal.")
    total = (subtotal - discount).quantize(CENT)

    payment_rows = []
    payment_total = Decimal("0.00")
    allowed_methods = {choice[0] for choice in SaleTender.Method.choices}
    for tender in tenders:
        if not isinstance(tender, dict):
            raise POSWorkflowError("As formas de pagamento são inválidas.")
        method = str(tender.get("method", ""))
        if method not in allowed_methods:
            raise POSWorkflowError("Forma de pagamento inválida.")
        amount = _money(tender.get("amount", "0"))
        if amount <= 0:
            raise POSWorkflowError("O valor de cada pagamento deve ser maior que zero.")
        payment_total += amount
        payment_rows.append(
            (
                method,
                amount,
                str(tender.get("reference", "")).strip()[:100],
            )
        )
    if payment_total != total:
        raise POSWorkflowError(
            "A soma dos pagamentos deve ser exatamente igual ao total da venda."
        )

    with transaction.atomic():
        register = CashRegister.objects.select_for_update().get(pk=register.pk)
        if not register.is_open:
            raise POSWorkflowError("O caixa foi fechado antes de salvar o rascunho.")
        if register.cashier_id != cashier.pk:
            raise POSWorkflowError("Este caixa pertence a outro operador.")
        sale = Sale.objects.create(
            register=register,
            cashier=cashier,
            customer=customer,
            subtotal=subtotal,
            discount_amount=discount,
            total=total,
        )
        SaleItem.objects.bulk_create(
            [
                SaleItem(
                    sale=sale,
                    product=product,
                    product_name=product.nome,
                    sku=product.sku,
                    is_service=product.eh_servico,
                    quantity=quantity,
                    unit_price=product.preco,
                    line_total=line_total,
                )
                for product, quantity, line_total in sale_lines
            ]
        )
        SaleTender.objects.bulk_create(
            [
                SaleTender(
                    sale=sale,
                    method=method,
                    amount=amount,
                    reference=reference,
                )
                for method, amount, reference in payment_rows
            ]
        )
    return sale


def cancel_draft_sale(sale, user, reason):
    reason = reason.strip()
    if not reason:
        raise POSWorkflowError("Informe o motivo do cancelamento.")
    if sale.cashier_id != user.pk and not user.has_perm("pdv.delete_sale"):
        raise POSWorkflowError("Você não pode cancelar o rascunho de outro operador.")
    with transaction.atomic():
        sale = Sale.objects.select_for_update().get(pk=sale.pk)
        if sale.status != Sale.Status.DRAFT:
            raise POSWorkflowError(
                "Somente vendas em preparação podem ser canceladas."
            )
        sale.status = Sale.Status.CANCELLED
        sale.cancel_reason = reason[:255]
        sale.cancelled_at = timezone.now()
        sale.save(update_fields=("status", "cancel_reason", "cancelled_at"))
    return sale
