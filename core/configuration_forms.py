import re
from pathlib import Path

from cryptography.hazmat.primitives.serialization import pkcs12
from django import forms
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils import timezone

from core.models import A1Certificate, CompanyProfile, SMTPConfiguration
from core.secure_storage import encrypt_bytes, encrypt_text, validate_encryption_key


class CompanyProfileForm(forms.ModelForm):
    cnpj = forms.CharField(
        label="CNPJ",
        max_length=18,
        help_text="Informe com ou sem pontuação; aceita o novo padrão alfanumérico.",
    )

    class Meta:
        model = CompanyProfile
        exclude = ("created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("primary_color", "sidebar_color", "accent_color"):
            self.fields[field_name].required = False
            self.fields[field_name].widget = forms.TextInput(
                attrs={"type": "color", "class": "vTextField"}
            )
        self.fields["logo"].widget.attrs["accept"] = "image/png,image/jpeg,image/webp"

    def clean_primary_color(self):
        return self.cleaned_data.get("primary_color") or (
            self.instance.primary_color
            if self.instance.pk
            else CompanyProfile._meta.get_field("primary_color").get_default()
        )

    def clean_accent_color(self):
        return self.cleaned_data.get("accent_color") or (
            self.instance.accent_color
            if self.instance.pk
            else CompanyProfile._meta.get_field("accent_color").get_default()
        )

    def clean_sidebar_color(self):
        return self.cleaned_data.get("sidebar_color") or (
            self.instance.sidebar_color
            if self.instance.pk
            else CompanyProfile._meta.get_field("sidebar_color").get_default()
        )

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if not logo or not hasattr(logo, "read"):
            return logo
        if logo.size > 2 * 1024 * 1024:
            raise ValidationError("O logo não pode exceder 2 MB.")
        if Path(logo.name).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValidationError("Envie um logo PNG, JPG ou WebP.")
        try:
            from PIL import Image

            image = Image.open(logo)
            image.verify()
            if image.width > 2048 or image.height > 2048:
                raise ValidationError("As dimensões do logo não podem exceder 2048 px.")
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError("O arquivo enviado não é uma imagem válida.") from exc
        finally:
            logo.seek(0)
        return logo

    def clean_cnpj(self):
        return re.sub(r"[\s./-]", "", self.cleaned_data["cnpj"]).upper()


class CompanyVisualIdentityForm(CompanyProfileForm):
    class Meta:
        model = CompanyProfile
        fields = (
            "legal_name",
            "trade_name",
            "cnpj",
            "logo",
            "primary_color",
            "sidebar_color",
            "accent_color",
        )


class SMTPConfigurationForm(forms.ModelForm):
    smtp_password = forms.CharField(
        label="Senha SMTP",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="A senha é criptografada e nunca é exibida. Em branco, mantém a senha atual.",
    )

    class Meta:
        model = SMTPConfiguration
        fields = (
            "host",
            "port",
            "username",
            "from_email",
            "use_tls",
            "use_ssl",
            "timeout",
            "is_active",
        )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("use_tls") and cleaned_data.get("use_ssl"):
            raise ValidationError("Use TLS ou SSL, não os dois ao mesmo tempo.")
        password = cleaned_data.get("smtp_password")
        if not self.instance.pk and not password:
            self.add_error("smtp_password", "Informe a senha SMTP.")
        elif cleaned_data.get("is_active") and not password and not self.instance.password_encrypted:
            self.add_error("smtp_password", "Informe a senha para ativar o SMTP.")
        if password:
            try:
                validate_encryption_key()
            except ImproperlyConfigured as exc:
                self.add_error("smtp_password", str(exc))
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        password = self.cleaned_data.get("smtp_password")
        if password:
            instance.password_encrypted = encrypt_text(password)
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class A1CertificateForm(forms.ModelForm):
    certificate_file = forms.FileField(
        label="Arquivo do certificado A1 (.pfx ou .p12)",
        required=False,
    )
    certificate_password = forms.CharField(
        label="Senha do certificado",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = A1Certificate
        fields = ()

    def clean_certificate_file(self):
        certificate_file = self.cleaned_data.get("certificate_file")
        if not certificate_file:
            return None
        if Path(certificate_file.name).suffix.lower() not in {".pfx", ".p12"}:
            raise ValidationError("Envie um arquivo .pfx ou .p12.")
        if certificate_file.size > 5 * 1024 * 1024:
            raise ValidationError("O arquivo do certificado não pode exceder 5 MB.")
        return certificate_file

    def clean(self):
        cleaned_data = super().clean()
        certificate_file = cleaned_data.get("certificate_file")
        password = cleaned_data.get("certificate_password")
        if not self.instance.pk and not certificate_file:
            self.add_error("certificate_file", "Selecione o certificado A1.")
            return cleaned_data
        if certificate_file and not password:
            self.add_error("certificate_password", "Informe a senha do certificado.")
            return cleaned_data
        if certificate_file:
            try:
                validate_encryption_key()
            except ImproperlyConfigured as exc:
                self.add_error("certificate_file", str(exc))
                return cleaned_data
        if not certificate_file:
            return cleaned_data

        data = certificate_file.read()
        certificate_file.seek(0)
        try:
            private_key, certificate, _additional = pkcs12.load_key_and_certificates(
                data,
                password.encode("utf-8"),
            )
        except (ValueError, TypeError) as exc:
            raise ValidationError(
                "Não foi possível validar o certificado. Confira o arquivo e a senha."
            ) from exc
        if private_key is None or certificate is None:
            raise ValidationError("O arquivo não contém um certificado A1 válido.")
        valid_until = certificate.not_valid_after_utc
        if valid_until <= timezone.now():
            raise ValidationError("O certificado A1 está vencido.")

        cleaned_data["certificate_payload"] = {
            "file": encrypt_bytes(data),
            "password": encrypt_text(password),
            "filename": Path(certificate_file.name).name[:255],
            "serial_number": str(certificate.serial_number),
            "valid_until": valid_until,
        }
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        payload = self.cleaned_data.get("certificate_payload")
        if payload:
            instance.encrypted_file = payload["file"]
            instance.encrypted_password = payload["password"]
            instance.original_filename = payload["filename"]
            instance.serial_number = payload["serial_number"]
            instance.valid_until = payload["valid_until"]
        if commit:
            instance.save()
            self.save_m2m()
        return instance
