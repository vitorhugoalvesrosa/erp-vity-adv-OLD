import smtplib

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from crm.models import Conta, Proposta
from financeiro.models import ContaReceber, Pagamento, PedidoVenda
from produtos.models import Produto
from .email_config import get_smtp_settings
from .forms import (
    ContaForm,
    ContaReceberForm,
    EmailNoticeForm,
    ERPPasswordResetForm,
    PagamentoForm,
    PedidoVendaForm,
    ProdutoForm,
    PropostaForm,
)


MODULES = {
    "contas": {
        "title": "Contas e clientes",
        "singular": "conta",
        "app": "crm",
        "model": Conta,
        "form": ContaForm,
        "columns": [
            ("nome", "Nome", "text"),
            ("documento", "Documento", "text"),
            ("email", "E-mail", "text"),
            ("status", "Etapa", "choice"),
        ],
        "search": ("nome", "documento", "email"),
        "select_related": (),
    },
    "propostas": {
        "title": "Propostas",
        "singular": "proposta",
        "app": "crm",
        "model": Proposta,
        "form": PropostaForm,
        "columns": [
            ("conta", "Conta", "text"),
            ("valor_total", "Valor", "currency"),
            ("condicao_pagamento", "Condição", "choice"),
            ("status", "Status", "choice"),
            ("data_validade", "Validade", "date"),
        ],
        "search": ("conta__nome",),
        "select_related": ("conta",),
    },
    "produtos": {
        "title": "Produtos e estoque",
        "singular": "produto",
        "app": "produtos",
        "model": Produto,
        "form": ProdutoForm,
        "columns": [
            ("nome", "Produto", "text"),
            ("sku", "SKU", "text"),
            ("preco", "Preço", "currency"),
            ("eh_servico", "Tipo", "service_type"),
            ("quantidade_estoque", "Estoque", "number"),
            ("ativo", "Status", "boolean"),
        ],
        "search": ("nome", "sku"),
        "select_related": (),
    },
    "pedidos": {
        "title": "Pedidos de venda",
        "singular": "pedido",
        "app": "financeiro",
        "model": PedidoVenda,
        "form": PedidoVendaForm,
        "columns": [
            ("proposta", "Proposta / cliente", "text"),
            ("valor_final", "Valor", "currency"),
            ("data_faturamento", "Faturamento", "date"),
        ],
        "search": ("proposta__conta__nome",),
        "select_related": ("proposta__conta",),
    },
    "recebiveis": {
        "title": "Contas a receber",
        "singular": "conta a receber",
        "app": "financeiro",
        "model": ContaReceber,
        "form": ContaReceberForm,
        "columns": [
            ("conta", "Cliente", "text"),
            ("pedido_venda", "Pedido", "text"),
            ("valor_parcela", "Valor", "currency"),
            ("data_vencimento", "Vencimento", "date"),
            ("status_pagamento", "Status", "choice"),
        ],
        "search": ("conta__nome",),
        "select_related": ("conta", "pedido_venda__proposta__conta"),
    },
    "pagamentos": {
        "title": "Pagamentos",
        "singular": "pagamento",
        "app": "financeiro",
        "model": Pagamento,
        "form": PagamentoForm,
        "columns": [
            ("conta_receber", "Conta", "text"),
            ("valor", "Valor", "currency"),
            ("data_pagamento", "Data", "date"),
            ("metodo_pagamento", "Método", "choice"),
        ],
        "search": ("conta_receber__conta__nome",),
        "select_related": ("conta_receber__conta",),
    },
}


@login_required
def home(request):
    def can_view(model):
        return request.user.has_perm(
            f"{model._meta.app_label}.view_{model._meta.model_name}"
        )
    stats = []
    if can_view(Conta):
        stats.append(
            {
                "label": "Contas no CRM",
                "value": Conta.objects.count(),
                "symbol": "CRM",
                "tone": "violet",
                "url": "record-list",
                "module": "contas",
            }
        )
    if can_view(Produto):
        stats.append(
            {
                "label": "Produtos ativos",
                "value": Produto.objects.filter(ativo=True).count(),
                "symbol": "SKU",
                "tone": "mint",
                "url": "record-list",
                "module": "produtos",
            }
        )
    if can_view(Proposta):
        stats.append(
            {
                "label": "Propostas em aberto",
                "value": Proposta.objects.filter(
                    status__in=[Proposta.Status.RASCUNHO, Proposta.Status.ENVIADA]
                ).count(),
                "symbol": "↗",
                "tone": "amber",
                "url": "record-list",
                "module": "propostas",
            }
        )

    open_receivables = ContaReceber.objects.exclude(
        status_pagamento=ContaReceber.StatusPagamento.PAGO
    )
    overdue_receivables = open_receivables.filter(
        data_vencimento__lt=timezone.localdate()
    )
    if can_view(ContaReceber):
        stats.append(
            {
                "label": "A receber",
                "value": open_receivables.aggregate(total=Sum("valor_parcela"))[
                    "total"
                ]
                or 0,
                "symbol": "R$",
                "tone": "blue",
                "kind": "currency",
                "url": "record-list",
                "module": "recebiveis",
            }
        )
    return render(
        request,
        "core/home.html",
        {
            "page_title": "Visão geral",
            "active_module": "dashboard",
            "stats": stats,
            "overdue_count": (
                overdue_receivables.count() if can_view(ContaReceber) else None
            ),
            "recent_proposals": (
                Proposta.objects.select_related("conta")[:5]
                if can_view(Proposta)
                else []
            ),
            "show_proposals": can_view(Proposta),
            "today": timezone.localdate(),
        },
    )


@login_required
def administration(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    return render(
        request,
        "core/administration.html",
        {
            "page_title": "Administração",
            "active_module": "administration",
        },
    )


def _get_module(module):
    try:
        return MODULES[module]
    except KeyError as exc:
        raise Http404("Módulo não encontrado.") from exc


def _require_permission(request, permission):
    if not request.user.has_perm(permission):
        raise PermissionDenied


def _get_columns(module, objects):
    rows = []
    for obj in objects:
        cells = []
        for field_name, _label, kind in module["columns"]:
            value = getattr(obj, field_name)
            display = getattr(obj, f"get_{field_name}_display", None)
            if field_name == "quantidade_estoque" and getattr(obj, "eh_servico", False):
                value = "Não controlado"
                kind = "text"
            elif kind == "service_type":
                value = "Serviço" if value else "Produto"
            elif display:
                value = display()
            elif kind == "boolean":
                value = "Ativo" if value else "Inativo"
            cells.append({"value": value, "kind": kind})
        rows.append({"object": obj, "cells": cells})
    return rows


@login_required
def record_list(request, module):
    config = _get_module(module)
    _require_permission(request, f"{config['app']}.view_{config['model']._meta.model_name}")

    queryset = config["model"].objects.all()
    if config["select_related"]:
        queryset = queryset.select_related(*config["select_related"])

    search = request.GET.get("q", "").strip()
    if search:
        query = Q()
        for field in config["search"]:
            query |= Q(**{f"{field}__icontains": search})
        queryset = queryset.filter(query)

    page_obj = Paginator(queryset, 20).get_page(request.GET.get("page"))
    permission_prefix = f"{config['app']}.{config['model']._meta.model_name}"
    return render(
        request,
        "core/record_list.html",
        {
            "page_title": config["title"],
            "active_module": module,
            "module": config,
            "columns": [column[1] for column in config["columns"]],
            "rows": _get_columns(config, page_obj.object_list),
            "page_obj": page_obj,
            "previous_page": (
                page_obj.previous_page_number() if page_obj.has_previous() else None
            ),
            "next_page": page_obj.next_page_number() if page_obj.has_next() else None,
            "search": search,
            "can_add": request.user.has_perm(
                f"{permission_prefix}.add_{config['model']._meta.model_name}"
            ),
            "can_change": request.user.has_perm(
                f"{permission_prefix}.change_{config['model']._meta.model_name}"
            ),
            "can_delete": request.user.has_perm(
                f"{permission_prefix}.delete_{config['model']._meta.model_name}"
            ),
        },
    )


@login_required
def record_edit(request, module, pk=None):
    config = _get_module(module)
    model_name = config["model"]._meta.model_name
    action = "change" if pk is not None else "add"
    _require_permission(request, f"{config['app']}.{action}_{model_name}")
    instance = get_object_or_404(config["model"], pk=pk) if pk is not None else None
    form = config["form"](
        request.POST if request.method == "POST" else None,
        instance=instance,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            f"{config['singular'].capitalize()} "
            f"{'atualizado' if instance else 'criado'} com sucesso.",
        )
        return redirect("record-list", module=module)

    return render(
        request,
        "core/record_form.html",
        {
            "page_title": f"{'Editar' if instance else 'Novo'} {config['singular']}",
            "active_module": module,
            "module": config,
            "form": form,
            "instance": instance,
        },
    )


@login_required
def record_delete(request, module, pk):
    config = _get_module(module)
    model_name = config["model"]._meta.model_name
    _require_permission(request, f"{config['app']}.delete_{model_name}")
    instance = get_object_or_404(config["model"], pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, f"{config['singular'].capitalize()} removido.")
        return redirect("record-list", module=module)

    return render(
        request,
        "core/record_confirm_delete.html",
        {
            "page_title": f"Excluir {config['singular']}",
            "active_module": module,
            "module": config,
            "instance": instance,
        },
    )


class ERPPasswordResetView(auth_views.PasswordResetView):
    template_name = "core/auth/password_reset_form.html"
    email_template_name = "core/auth/password_reset_email.html"
    subject_template_name = "core/auth/password_reset_subject.txt"
    form_class = ERPPasswordResetForm
    success_url = reverse_lazy("password_reset_done")

    def form_valid(self, form):
        try:
            smtp_settings = get_smtp_settings()
        except ImproperlyConfigured:
            form.add_error(
                None,
                "Não foi possível ler a configuração SMTP criptografada. "
                "Verifique CONFIG_ENCRYPTION_KEY no ambiente.",
            )
            return self.form_invalid(form)
        if not smtp_settings.is_configured:
            form.add_error(
                None,
                "O envio de e-mails ainda não está configurado neste ambiente.",
            )
            return self.form_invalid(form)

        try:
            self.from_email = smtp_settings.from_email
            return super().form_valid(form)
        except (OSError, smtplib.SMTPException) as exc:
            form.add_error(None, f"Não foi possível enviar o e-mail: {exc}")
            return self.form_invalid(form)


class ERPPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "core/auth/password_reset_confirm.html"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.widget.attrs.update(
                {"class": "form-control", "autocomplete": "new-password"}
            )
        return form


@login_required
def send_notice(request):
    if not (request.user.is_superuser or request.user.has_perm("auth.change_user")):
        raise PermissionDenied

    form = EmailNoticeForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            smtp_settings = get_smtp_settings()
        except ImproperlyConfigured:
            form.add_error(
                None,
                "Não foi possível ler a configuração SMTP criptografada. "
                "Verifique CONFIG_ENCRYPTION_KEY no ambiente.",
            )
            smtp_settings = None
        if smtp_settings is not None:
            if not smtp_settings.is_configured:
                form.add_error(
                    None,
                    "O envio de e-mails ainda não está configurado neste ambiente.",
                )
            else:
                recipients = list(form.cleaned_data["recipients"])
                email = EmailMessage(
                    subject=form.cleaned_data["subject"],
                    body=form.cleaned_data["message"],
                    from_email=smtp_settings.from_email,
                    to=[smtp_settings.from_email],
                    bcc=[user.email for user in recipients],
                )
                try:
                    sent = email.send(fail_silently=False)
                except (OSError, smtplib.SMTPException) as exc:
                    form.add_error(None, f"Não foi possível enviar o e-mail: {exc}")
                else:
                    if sent == 1:
                        messages.success(
                            request,
                            f"Comunicado enviado para {len(recipients)} usuário(s).",
                        )
                        return redirect("send-email-notice")
                    form.add_error(None, "O servidor de e-mail não aceitou o envio.")

    return render(
        request,
        "core/email_notice_form.html",
        {"form": form, "page_title": "Enviar comunicado", "active_module": "email"},
    )
