from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm

from crm.models import Conta, Proposta
from financeiro.models import ContaReceber, Pagamento, PedidoVenda
from produtos.models import Produto


class ERPAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "form-control", "autocomplete": "username"}
        )
        self.fields["password"].widget.attrs.update(
            {"class": "form-control", "autocomplete": "current-password"}
        )


class ERPPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {"class": "form-control", "autocomplete": "email"}
        )


class ERPModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-checkbox"
            elif isinstance(field, forms.DateField):
                field.widget.input_type = "date"
                field.widget.attrs["class"] = "form-control"
            elif isinstance(field, forms.DecimalField):
                field.widget.attrs.update({"class": "form-control", "step": "0.01"})
            elif isinstance(field, forms.IntegerField):
                field.widget.attrs.update({"class": "form-control", "step": "1"})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"


class ContaForm(ERPModelForm):
    class Meta:
        model = Conta
        fields = ("nome", "documento", "email", "telefone", "status")


class PropostaForm(ERPModelForm):
    class Meta:
        model = Proposta
        fields = ("conta", "valor_total", "condicao_pagamento", "status", "data_validade")


class ProdutoForm(ERPModelForm):
    class Meta:
        model = Produto
        fields = (
            "nome",
            "descricao",
            "sku",
            "preco",
            "eh_servico",
            "quantidade_estoque",
            "ativo",
        )


class PedidoVendaForm(ERPModelForm):
    class Meta:
        model = PedidoVenda
        fields = ("proposta", "valor_final", "data_faturamento")


class ContaReceberForm(ERPModelForm):
    class Meta:
        model = ContaReceber
        fields = (
            "conta",
            "pedido_venda",
            "valor_parcela",
            "data_vencimento",
            "status_pagamento",
        )


class PagamentoForm(ERPModelForm):
    class Meta:
        model = Pagamento
        fields = ("conta_receber", "valor", "data_pagamento", "metodo_pagamento")


class EmailNoticeForm(forms.Form):
    recipients = forms.ModelMultipleChoiceField(
        queryset=get_user_model().objects.none(),
        label="Destinatários",
        help_text="Somente usuários ativos com endereço de e-mail cadastrado.",
    )
    subject = forms.CharField(label="Assunto", max_length=200)
    message = forms.CharField(
        label="Mensagem",
        widget=forms.Textarea(attrs={"rows": 8}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["recipients"].queryset = get_user_model().objects.filter(
            is_active=True,
            email__gt="",
        ).order_by("username")
        self.fields["recipients"].widget.attrs["class"] = "form-select form-select-multiple"
        self.fields["subject"].widget.attrs["class"] = "form-control"
        self.fields["message"].widget.attrs["class"] = "form-control"

    def clean_subject(self):
        subject = self.cleaned_data["subject"]
        if "\r" in subject or "\n" in subject:
            raise forms.ValidationError("O assunto deve estar em uma única linha.")
        return subject
