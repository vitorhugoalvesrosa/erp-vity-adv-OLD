import smtplib
from io import BytesIO
from mimetypes import guess_type
from xml.sax.saxutils import escape

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from crm.models import Conta, Proposta
from financeiro.models import Contrato, ContaReceber, Pagamento, PedidoVenda
from produtos.models import Produto
from .email_config import get_smtp_settings
from .configuration_forms import CompanyVisualIdentityForm
from .forms import (
    ContaForm,
    ContaReceberForm,
    ContratoForm,
    EmailNoticeForm,
    ERPPasswordResetForm,
    PagamentoForm,
    PedidoVendaForm,
    ProdutoForm,
    PropostaForm,
)
from .models import CompanyProfile


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
        "title": "Orçamentos",
        "singular": "orçamento",
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
        "title": "Produtos, estoque e serviços",
        "singular": "produto",
        "app": "produtos",
        "model": Produto,
        "form": ProdutoForm,
        "columns": [
            ("nome", "Produto", "text"),
            ("sku", "SKU", "text"),
            ("preco", "Preço", "currency"),
            ("eh_servico", "Tipo", "service_type"),
            ("categoria_estetica", "Categoria", "choice"),
            ("duracao_minutos", "Duração", "number"),
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
    "contratos": {
        "title": "Contratos",
        "singular": "contrato",
        "app": "financeiro",
        "model": Contrato,
        "form": ContratoForm,
        "columns": [
            ("number", "Contrato", "text"),
            ("cliente", "Cliente", "text"),
            ("status", "Status", "choice"),
            ("start_date", "Início", "date"),
            ("end_date", "Fim", "date"),
        ],
        "search": ("pedido_venda__proposta__conta__nome",),
        "select_related": ("pedido_venda__proposta__conta",),
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


@login_required
def visual_identity(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    profile = CompanyProfile.objects.first()
    form = CompanyVisualIdentityForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        instance=profile,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Identidade visual atualizada com sucesso.")
        return redirect("visual-identity")

    return render(
        request,
        "core/visual_identity_form.html",
        {
            "page_title": "Identidade visual",
            "active_module": "administration",
            "form": form,
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
    rows = _get_columns(config, page_obj.object_list)
    can_generate_order = module == "propostas" and request.user.has_perm(
        "financeiro.add_pedidovenda"
    )
    can_generate_contract = module == "pedidos" and request.user.has_perm(
        "financeiro.add_contrato"
    )
    if can_generate_order:
        existing_orders = dict(
            PedidoVenda.objects.filter(
                proposta_id__in=[row["object"].pk for row in rows]
            ).values_list("proposta_id", "pk")
        )
        for row in rows:
            row["order_id"] = existing_orders.get(row["object"].pk)
            row["can_generate_order"] = (
                row["object"].status == Proposta.Status.GANHA
                and row["order_id"] is None
            )
    if can_generate_contract:
        existing_orders = set(
            Contrato.objects.filter(
                pedido_venda_id__in=[row["object"].pk for row in rows]
            ).values_list("pedido_venda_id", flat=True)
        )
        for row in rows:
            row["can_generate_contract"] = (
                row["object"].proposta.status == Proposta.Status.GANHA
                and row["object"].pk not in existing_orders
            )
    return render(
        request,
        "core/record_list.html",
        {
            "page_title": config["title"],
            "active_module": module,
            "module": config,
            "columns": [column[1] for column in config["columns"]],
            "rows": rows,
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
            "can_generate_order": can_generate_order,
            "can_generate_contract": can_generate_contract,
        },
    )


@login_required
def record_edit(request, module, pk=None):
    config = _get_module(module)
    model_name = config["model"]._meta.model_name
    action = "change" if pk is not None else "add"
    _require_permission(request, f"{config['app']}.{action}_{model_name}")
    instance = get_object_or_404(config["model"], pk=pk) if pk is not None else None
    form_kwargs = {
        "data": request.POST if request.method == "POST" else None,
        "instance": instance,
    }
    if module == "contratos" and not instance and request.GET.get("pedido_id"):
        form_kwargs["initial"] = {"pedido_venda": request.GET["pedido_id"]}
    form = config["form"](**form_kwargs)
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
@require_POST
def generate_sale_order(request, proposal_id):
    _require_permission(request, "crm.view_proposta")
    _require_permission(request, "financeiro.add_pedidovenda")
    with transaction.atomic():
        proposal = get_object_or_404(
            Proposta.objects.select_for_update(), pk=proposal_id
        )
        if proposal.status != Proposta.Status.GANHA:
            messages.error(request, "Apenas orçamentos aprovados podem gerar pedidos.")
            return redirect("record-list", module="propostas")
        order, created = PedidoVenda.objects.get_or_create(
            proposta=proposal,
            defaults={
                "valor_final": proposal.valor_total,
                "data_faturamento": timezone.localdate(),
            },
        )
    if created:
        messages.success(request, f"Pedido de venda {order.pk} gerado com sucesso.")
    else:
        messages.info(request, f"Este orçamento já possui o pedido {order.pk}.")
    return redirect("record-list", module="pedidos")


def _format_currency(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_date(value):
    return value.strftime("%d/%m/%Y") if value else "Indeterminado"


@login_required
def contract_pdf(request, pk):
    _require_permission(request, "financeiro.view_contrato")
    contract = get_object_or_404(
        Contrato.objects.select_related("pedido_venda__proposta__conta"), pk=pk
    )
    company = CompanyProfile.objects.first()
    client = contract.pedido_venda.proposta.conta
    order = contract.pedido_venda
    primary = colors.HexColor(company.primary_color if company else "#34465A")
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"Contrato de Prestação de Serviços {contract.number}",
        author=(company.trade_name or company.legal_name) if company else "ERP Vity",
    )
    base_styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ContractTitle",
        parent=base_styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=primary,
        alignment=TA_CENTER,
        spaceAfter=5 * mm,
    )
    section_style = ParagraphStyle(
        "ContractSection",
        parent=base_styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=primary,
        spaceBefore=4 * mm,
        spaceAfter=1.5 * mm,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "ContractBody",
        parent=base_styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        alignment=TA_JUSTIFY,
        spaceAfter=2.5 * mm,
    )
    detail_style = ParagraphStyle(
        "ContractDetail",
        parent=body_style,
        alignment=0,
        spaceAfter=0,
    )

    def paragraph(value, style=body_style):
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), style)

    company_name = (company.trade_name or company.legal_name) if company else "Prestador de serviços"
    company_document = company.cnpj if company else "Não informado"
    company_address = ""
    if company:
        company_address = ", ".join(
            value
            for value in (
                " ".join(part for part in (company.street, company.street_number) if part),
                company.neighborhood,
                f"{company.city}/{company.state}",
                company.postal_code,
            )
            if value
        )
    client_representative = contract.client_representative or "representante legal"
    story = []
    logo_stream = None
    if company and company.logo:
        logo_stream = BytesIO(company.logo.read())
        story.append(Image(logo_stream, width=42 * mm, height=20 * mm, kind="proportional"))
        story.append(Spacer(1, 4 * mm))
    story.extend(
        [
            paragraph("CONTRATO DE PRESTAÇÃO DE SERVIÇOS", title_style),
            paragraph(f"{contract.number} | Minuta padrão v1.0", detail_style),
            Spacer(1, 4 * mm),
            paragraph(
                f"Pelo presente instrumento, de um lado, {company_name}, "
                f"inscrita no CNPJ sob nº {company_document}"
                f"{', com sede em ' + company_address if company_address else ''}, "
                "doravante denominada CONTRATADA; e, de outro lado, "
                f"{client.nome}, inscrita no CPF/CNPJ sob nº "
                f"{client.documento}, doravante denominada CONTRATANTE, "
                "resolvem celebrar este contrato, conforme as cláusulas abaixo.",
            ),
        ]
    )
    details = [
        [paragraph("Pedido de venda", detail_style), paragraph(str(order.pk), detail_style)],
        [paragraph("Valor total", detail_style), paragraph(_format_currency(order.valor_final), detail_style)],
        [paragraph("Data do contrato", detail_style), paragraph(_format_date(contract.contract_date), detail_style)],
        [paragraph("Vigência", detail_style), paragraph(f"{_format_date(contract.start_date)} a {_format_date(contract.end_date)}", detail_style)],
    ]
    details_table = Table(details, colWidths=[42 * mm, 118 * mm], hAlign="LEFT")
    details_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F4F7")),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#DCE2E8")),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#DCE2E8")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([Spacer(1, 3 * mm), details_table])
    clauses = [
        (
            "1. OBJETO E ESCOPO",
            f"A CONTRATADA prestará os seguintes serviços: {contract.service_description}. "
            f"A execução ocorrerá em {contract.service_location or 'local a ser acordado entre as partes'}, "
            "observadas as especificações, entregáveis e critérios de aceite descritos neste instrumento "
            "e no orçamento aprovado que originou o pedido de venda.",
        ),
        (
            "2. OBRIGAÇÕES DA CONTRATADA",
            "Executar os serviços com diligência e observância do escopo acordado; manter a CONTRATANTE "
            "informada sobre o andamento e comunicar tempestivamente riscos ou impedimentos; corrigir, "
            "em prazo razoável, desconformidades comprovadamente atribuíveis à execução contratada; e "
            "manter as licenças e qualificações necessárias à sua atividade.",
        ),
        (
            "3. OBRIGAÇÕES DA CONTRATANTE",
            "Fornecer informações, acessos, aprovações e recursos necessários à execução; indicar pessoa "
            "responsável pelo acompanhamento; avaliar entregáveis em prazo razoável; e efetuar os pagamentos "
            "nas condições pactuadas. Atrasos decorrentes de dependências da CONTRATANTE poderão ajustar "
            "o cronograma mediante comunicação entre as partes.",
        ),
        (
            "4. PREÇO E PAGAMENTO",
            f"Pelos serviços, a CONTRATANTE pagará {_format_currency(order.valor_final)}, conforme: "
            f"{contract.payment_terms}. A emissão de documentos fiscais observará a legislação aplicável. "
            "Despesas extraordinárias somente serão reembolsáveis quando previamente aprovadas por escrito.",
        ),
        (
            "5. PRAZO E VIGÊNCIA",
            f"A vigência inicia em {_format_date(contract.start_date)} e termina em "
            f"{_format_date(contract.end_date)}. A continuidade ou prorrogação dependerá de acordo escrito "
            "entre as partes, inclusive quanto a escopo, preço e cronograma.",
        ),
        (
            "6. CONFIDENCIALIDADE",
            "As partes manterão em sigilo as informações confidenciais recebidas em razão deste contrato, "
            "utilizando-as apenas para sua execução e limitando o acesso a quem necessite conhecê-las. "
            "A obrigação não abrange informações públicas, obtidas legitimamente de terceiros ou cuja "
            "divulgação seja exigida por lei, hipótese em que a outra parte será avisada quando permitido.",
        ),
        (
            "7. PROTEÇÃO DE DADOS",
            "As partes tratarão dados pessoais somente na medida necessária à execução contratual e em "
            "conformidade com a Lei nº 13.709/2018 (LGPD), adotando medidas técnicas e administrativas "
            "proporcionais para protegê-los. Cada parte responderá pelos tratamentos sob sua responsabilidade "
            "e comunicará incidentes relevantes à outra parte sem demora injustificada.",
        ),
        (
            "8. PROPRIEDADE INTELECTUAL",
            "Materiais, ferramentas, métodos e conhecimentos preexistentes permanecem de titularidade de "
            "seus respectivos titulares. A titularidade ou licença de uso dos entregáveis produzidos sob "
            "encomenda deverá observar o escopo e as condições comerciais acordadas por escrito entre as partes.",
        ),
        (
            "9. RESPONSABILIDADE E CASO FORTUITO",
            "Cada parte responderá pelos danos diretos que causar por descumprimento comprovado de suas "
            "obrigações, observados os limites permitidos pela legislação. Nenhuma parte será responsável "
            "por atraso causado por evento de força maior ou caso fortuito enquanto durar o impedimento, "
            "desde que comunique a outra parte e adote medidas razoáveis para mitigar seus efeitos.",
        ),
        (
            "10. RESCISÃO",
            f"O contrato poderá ser rescindido por qualquer parte mediante aviso escrito com antecedência "
            f"mínima de {contract.termination_notice_days} dias. O descumprimento material não sanado em "
            "prazo razoável após notificação também poderá ensejar rescisão. Permanecem devidos os valores "
            "proporcionais aos serviços executados e despesas previamente aprovadas até a data de término.",
        ),
        (
            "11. DISPOSIÇÕES GERAIS E ASSINATURA",
            "Alterações somente terão validade se formalizadas por escrito. A eventual tolerância não implica "
            "renúncia de direito. As partes admitem assinatura física ou eletrônica, observada a legislação "
            "aplicável e a possibilidade de comprovação de autoria e integridade do documento.",
        ),
        (
            "12. FORO",
            f"Fica eleito o foro da comarca de {company.city if company else 'cidade a preencher'}"
            f"/{company.state if company else 'UF'}, ressalvadas as hipóteses legais de competência obrigatória, "
            "para dirimir controvérsias decorrentes deste contrato.",
        ),
    ]
    for heading, text in clauses:
        story.append(KeepTogether([paragraph(heading, section_style), paragraph(text)]))
    if contract.additional_clauses:
        story.extend(
            [
                paragraph("13. CONDIÇÕES ADICIONAIS", section_style),
                paragraph(contract.additional_clauses),
            ]
        )
    story.extend(
        [
            Spacer(1, 8 * mm),
            paragraph(
                f"E, por estarem de acordo, as partes assinam este instrumento em "
                f"{escape(company.city if company else '________________')}"
                f"/{escape(company.state if company else '___')}, em "
                f"{_format_date(contract.contract_date)}.",
            ),
            Spacer(1, 17 * mm),
            Table(
                [
                    ["____________________________________", "____________________________________"],
                    [escape(company_name), escape(client.nome)],
                    ["CONTRATADA", f"CONTRATANTE - {escape(client_representative)}"],
                    [f"CNPJ: {escape(company_document)}", f"CPF/CNPJ: {escape(client.documento)}"],
                ],
                colWidths=[80 * mm, 80 * mm],
                style=TableStyle(
                    [
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 1), (-1, 2), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ]
                ),
            ),
            Spacer(1, 10 * mm),
            paragraph(
                "Minuta padrão para servir de ponto de partida. Recomenda-se revisão jurídica "
                "e adequação ao serviço, à operação e à legislação aplicável antes da assinatura.",
                detail_style,
            ),
        ]
    )

    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(primary)
        canvas.setLineWidth(0.6)
        canvas.line(22 * mm, 15 * mm, A4[0] - 22 * mm, 15 * mm)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.setFont("Helvetica", 8)
        canvas.drawString(22 * mm, 10 * mm, contract.number)
        canvas.drawRightString(A4[0] - 22 * mm, 10 * mm, f"Página {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{contract.number}.pdf"'
    return response


def company_logo(request):
    company = CompanyProfile.objects.first()
    if not company or not company.logo:
        raise Http404("Logo não configurado.")
    return FileResponse(
        company.logo.open("rb"),
        content_type=guess_type(company.logo.name)[0] or "application/octet-stream",
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
