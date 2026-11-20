from django import forms
from django.contrib.auth import get_user_model


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

    def clean_subject(self):
        subject = self.cleaned_data["subject"]
        if "\r" in subject or "\n" in subject:
            raise forms.ValidationError("O assunto deve estar em uma única linha.")
        return subject
