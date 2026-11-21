import smtplib

from django.contrib import admin, messages
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import get_connection

from core.admin_site import erp_admin_site
from core.configuration_forms import (
    A1CertificateForm,
    CompanyProfileForm,
    SMTPConfigurationForm,
)
from core.models import A1Certificate, CompanyProfile, SMTPConfiguration
from core.secure_storage import decrypt_text


@admin.register(CompanyProfile, site=erp_admin_site)
class CompanyProfileAdmin(admin.ModelAdmin):
    form = CompanyProfileForm
    list_display = ("legal_name", "cnpj", "city", "state", "tax_regime")
    fieldsets = (
        (
            "Identificação",
            {
                "fields": (
                    "legal_name",
                    "trade_name",
                    "cnpj",
                    "tax_regime",
                    "cnae",
                    "municipal_registration",
                    "state_registration",
                )
            },
        ),
        (
            "Endereço",
            {
                "fields": (
                    "postal_code",
                    "street",
                    "street_number",
                    "address_complement",
                    "neighborhood",
                    "city",
                    "state",
                )
            },
        ),
        ("Contato", {"fields": ("phone", "email")}),
        (
            "Identidade visual",
            {"fields": ("logo", "primary_color", "accent_color")},
        ),
    )

    def has_add_permission(self, request):
        return not CompanyProfile.objects.exists()


@admin.action(description="Testar autenticação SMTP")
def test_smtp_connection(modeladmin, request, queryset):
    if queryset.count() != 1:
        modeladmin.message_user(
            request,
            "Selecione uma única configuração SMTP.",
            level=messages.ERROR,
        )
        return

    configuration = queryset.first()
    if not configuration.password_encrypted:
        modeladmin.message_user(
            request,
            "SMTP incompleto. Configure servidor, usuário, senha e remetente.",
            level=messages.ERROR,
        )
        return

    try:
        password = decrypt_text(configuration.password_encrypted)
    except ImproperlyConfigured as exc:
        modeladmin.message_user(
            request,
            str(exc),
            level=messages.ERROR,
        )
        return
    connection = get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=configuration.host,
        port=configuration.port,
        username=configuration.username,
        password=password,
        use_tls=configuration.use_tls,
        use_ssl=configuration.use_ssl,
        timeout=configuration.timeout,
    )
    try:
        opened = connection.open()
    except (OSError, smtplib.SMTPException) as exc:
        modeladmin.message_user(
            request,
            f"Falha ao autenticar no servidor SMTP: {exc}",
            level=messages.ERROR,
        )
    else:
        if opened:
            connection.close()
            modeladmin.message_user(
                request,
                "Autenticação SMTP concluída com sucesso.",
                level=messages.SUCCESS,
            )
        else:
            modeladmin.message_user(
                request,
                "Não foi possível abrir a conexão SMTP.",
                level=messages.ERROR,
            )


@admin.register(SMTPConfiguration, site=erp_admin_site)
class SMTPConfigurationAdmin(admin.ModelAdmin):
    form = SMTPConfigurationForm
    list_display = ("from_email", "host", "port", "is_active", "updated_at")
    fields = (
        "host",
        "port",
        "username",
        "smtp_password",
        "from_email",
        "use_tls",
        "use_ssl",
        "timeout",
        "is_active",
    )
    actions = (test_smtp_connection,)

    def has_add_permission(self, request):
        return not SMTPConfiguration.objects.exists()


@admin.register(A1Certificate, site=erp_admin_site)
class A1CertificateAdmin(admin.ModelAdmin):
    form = A1CertificateForm
    list_display = ("original_filename", "serial_number", "valid_until", "uploaded_at")
    readonly_fields = ("original_filename", "serial_number", "valid_until", "uploaded_at")
    fields = (
        "certificate_file",
        "certificate_password",
        "original_filename",
        "serial_number",
        "valid_until",
        "uploaded_at",
    )

    def has_add_permission(self, request):
        return not A1Certificate.objects.exists()
