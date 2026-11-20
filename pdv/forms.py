from django import forms

from crm.models import Conta
from .models import CashMovement


class RegisterOpenForm(forms.Form):
    opening_amount = forms.DecimalField(
        label="Fundo de abertura",
        min_value=0,
        max_digits=12,
        decimal_places=2,
        initial=0,
    )


class RegisterCloseForm(forms.Form):
    counted_amount = forms.DecimalField(
        label="Dinheiro contado no caixa",
        min_value=0,
        max_digits=12,
        decimal_places=2,
    )


class CashMovementForm(forms.Form):
    direction = forms.ChoiceField(
        label="Movimentação",
        choices=(
            (CashMovement.Direction.IN, "Suprimento"),
            (CashMovement.Direction.OUT, "Sangria"),
        ),
    )
    amount = forms.DecimalField(
        label="Valor",
        min_value="0.01",
        max_digits=12,
        decimal_places=2,
    )
    description = forms.CharField(label="Motivo", max_length=255)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["direction"].widget.attrs["class"] = "form-select"
        self.fields["description"].widget.attrs["class"] = "form-control"


class SaleDraftForm(forms.Form):
    items = forms.JSONField(widget=forms.HiddenInput)
    tenders = forms.JSONField(widget=forms.HiddenInput)
    customer = forms.ModelChoiceField(
        label="Cliente (opcional)",
        queryset=Conta.objects.order_by("nome"),
        required=False,
    )
    discount_amount = forms.DecimalField(
        label="Desconto total (R$)",
        min_value=0,
        max_digits=12,
        decimal_places=2,
        initial=0,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].widget.attrs["class"] = "form-select"

    def clean_items(self):
        items = self.cleaned_data["items"]
        if not isinstance(items, list):
            raise forms.ValidationError("Os itens da venda são inválidos.")
        return items

    def clean_tenders(self):
        tenders = self.cleaned_data["tenders"]
        if not isinstance(tenders, list):
            raise forms.ValidationError("As formas de pagamento são inválidas.")
        return tenders


class DraftCancelForm(forms.Form):
    reason = forms.CharField(label="Motivo do cancelamento", max_length=255)
