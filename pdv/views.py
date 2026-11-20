from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from crm.models import Conta
from produtos.models import Produto

from .forms import (
    CashMovementForm,
    DraftCancelForm,
    RegisterCloseForm,
    RegisterOpenForm,
    SaleDraftForm,
)
from .models import CashMovement, CashRegister, Sale
from .services import (
    POSWorkflowError,
    cancel_draft_sale,
    close_register as close_register_service,
    complete_sale,
    create_draft_sale,
    expected_cash,
    open_register as open_register_service,
    record_cash_movement,
)


FISCAL_PENDING_MESSAGE = (
    "O PDV funciona sem cadastro fiscal ou comunicação com a SEFAZ. "
    "As vendas são registradas no ERP; a emissão de documentos fiscais "
    "permanece pendente e não é realizada por este módulo."
)


def _require_permission(user, permission):
    if not user.has_perm(permission):
        raise PermissionDenied


def _open_register_for(user):
    return CashRegister.objects.filter(
        cashier=user,
        closed_at__isnull=True,
    ).first()


@login_required
def terminal(request):
    _require_permission(request.user, "pdv.view_sale")
    register = _open_register_for(request.user)
    if register:
        products = Produto.objects.filter(ativo=True).order_by("nome")
        draft_form = SaleDraftForm()
        if not request.user.has_perm("crm.view_conta"):
            draft_form.fields["customer"].queryset = Conta.objects.none()
        context = {
            "register": register,
            "expected_cash": expected_cash(register),
            "movements": register.movements.all()[:10],
            "draft_sales": register.sales.filter(status=Sale.Status.DRAFT).prefetch_related(
                "items",
                "tenders",
            ),
            "completed_sales": register.sales.filter(
                status=Sale.Status.COMPLETED,
            ).prefetch_related("items", "tenders")[:10],
            "product_data": [
                {
                    "sku": product.sku,
                    "name": product.nome,
                    "price": str(product.preco),
                    "stock": product.quantidade_estoque,
                    "is_service": product.eh_servico,
                }
                for product in products
            ],
            "open_form": None,
            "close_form": RegisterCloseForm(),
            "movement_form": CashMovementForm(),
            "draft_form": draft_form,
            "can_open": False,
            "can_close": request.user.has_perm("pdv.change_cashregister"),
            "can_move_cash": request.user.has_perm("pdv.add_cashmovement"),
            "can_create_sale": request.user.has_perm("pdv.add_sale"),
            "can_cancel_any": request.user.has_perm("pdv.delete_sale"),
        }
    else:
        context = {
            "register": None,
            "expected_cash": None,
            "movements": (),
            "draft_sales": (),
            "completed_sales": (),
            "product_data": (),
            "open_form": RegisterOpenForm(),
            "close_form": None,
            "movement_form": None,
            "draft_form": None,
            "can_open": request.user.has_perm("pdv.add_cashregister"),
            "can_close": False,
            "can_move_cash": False,
            "can_create_sale": False,
            "can_cancel_any": request.user.has_perm("pdv.delete_sale"),
        }
    context.update(
        {
            "page_title": "PDV",
            "active_module": "pdv",
            "fiscal_pending_message": FISCAL_PENDING_MESSAGE,
        }
    )
    return render(request, "pdv/terminal.html", context)


@login_required
@require_POST
def open_register(request):
    _require_permission(request.user, "pdv.add_cashregister")
    form = RegisterOpenForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Informe um fundo de abertura válido.")
        return redirect("pdv:terminal")
    try:
        open_register_service(
            request.user,
            form.cleaned_data["opening_amount"],
        )
    except POSWorkflowError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Caixa aberto.")
    return redirect("pdv:terminal")


@login_required
@require_POST
def close_register(request):
    _require_permission(request.user, "pdv.change_cashregister")
    register = _open_register_for(request.user)
    if register is None:
        messages.error(request, "Não há caixa aberto para fechar.")
        return redirect("pdv:terminal")
    form = RegisterCloseForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Informe o valor contado para fechar o caixa.")
        return redirect("pdv:terminal")
    try:
        closed_register = close_register_service(
            register,
            form.cleaned_data["counted_amount"],
        )
    except POSWorkflowError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            "Caixa fechado. "
            f"Esperado: R$ {closed_register.expected_amount:.2f}; "
            f"contado: R$ {closed_register.counted_amount:.2f}.",
        )
    return redirect("pdv:terminal")


@login_required
@require_POST
def cash_movement(request):
    _require_permission(request.user, "pdv.add_cashmovement")
    register = _open_register_for(request.user)
    if register is None:
        messages.error(request, "Abra o caixa antes de registrar movimentações.")
        return redirect("pdv:terminal")
    form = CashMovementForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Revise os dados da movimentação.")
        return redirect("pdv:terminal")
    try:
        record_cash_movement(
            register,
            request.user,
            form.cleaned_data["direction"],
            form.cleaned_data["amount"],
            form.cleaned_data["description"],
        )
    except POSWorkflowError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Movimentação registrada.")
    return redirect("pdv:terminal")


@login_required
@require_POST
def create_draft(request):
    _require_permission(request.user, "pdv.add_sale")
    register = _open_register_for(request.user)
    if register is None:
        messages.error(request, "Abra o caixa antes de preparar uma venda.")
        return redirect("pdv:terminal")
    form = SaleDraftForm(request.POST)
    if not request.user.has_perm("crm.view_conta"):
        form.fields["customer"].queryset = Conta.objects.none()
    if not form.is_valid():
        messages.error(request, "Revise os itens, valores e formas de pagamento.")
        return redirect("pdv:terminal")
    try:
        sale = create_draft_sale(
            register=register,
            cashier=request.user,
            lines=form.cleaned_data["items"],
            tenders=form.cleaned_data["tenders"],
            discount_amount=form.cleaned_data["discount_amount"],
            customer=form.cleaned_data["customer"],
        )
    except POSWorkflowError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f"Pré-venda #{sale.pk} salva. Conclua a venda para registrar pagamento e estoque.",
        )
    return redirect("pdv:terminal")


@login_required
@require_POST
def finalize_sale(request, pk):
    _require_permission(request.user, "pdv.add_sale")
    sale = get_object_or_404(Sale, pk=pk, status=Sale.Status.DRAFT)
    if sale.cashier_id != request.user.pk and not request.user.has_perm("pdv.delete_sale"):
        raise PermissionDenied
    try:
        completed_sale = complete_sale(sale, request.user)
    except POSWorkflowError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f"Venda #{completed_sale.pk} registrada no ERP. "
            "Emissão fiscal pendente; nenhum documento fiscal foi emitido.",
        )
    return redirect("pdv:terminal")


@login_required
@require_POST
def cancel_draft(request, pk):
    _require_permission(request.user, "pdv.add_sale")
    sale = get_object_or_404(Sale, pk=pk)
    form = DraftCancelForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Informe o motivo do cancelamento.")
        return redirect("pdv:terminal")
    try:
        cancel_draft_sale(
            sale,
            request.user,
            form.cleaned_data["reason"],
        )
    except POSWorkflowError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Pré-venda #{sale.pk} cancelada.")
    return redirect("pdv:terminal")
