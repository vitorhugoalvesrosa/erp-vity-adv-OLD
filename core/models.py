from django.core.validators import RegexValidator
from django.db import models


class ERPUserBootstrap(models.Model):
    name = models.CharField(max_length=50, unique=True)
    completed_at = models.DateTimeField(auto_now_add=True)


class ERPAdminPasswordReset(models.Model):
    token_hash = models.CharField(max_length=64, unique=True)
    completed_at = models.DateTimeField(auto_now_add=True)


class CompanyProfile(models.Model):
    class TaxRegime(models.TextChoices):
        MEI = "mei", "MEI"
        SIMPLES = "simples", "Simples Nacional"
        PRESUMIDO = "presumido", "Lucro Presumido"
        REAL = "real", "Lucro Real"

    legal_name = models.CharField("Razão social", max_length=255)
    trade_name = models.CharField("Nome fantasia", max_length=255, blank=True)
    cnpj = models.CharField(
        "CNPJ",
        max_length=18,
        unique=True,
        validators=[
            RegexValidator(
                r"^[A-Za-z0-9]{12}\d{2}$",
                "Informe o CNPJ com 14 caracteres, sem pontuação.",
            )
        ],
        help_text="Informe os 14 caracteres sem pontuação; aceita o novo padrão alfanumérico.",
    )
    municipal_registration = models.CharField(
        "Inscrição municipal",
        max_length=40,
        blank=True,
    )
    state_registration = models.CharField(
        "Inscrição estadual",
        max_length=40,
        blank=True,
    )
    tax_regime = models.CharField(
        "Regime tributário",
        max_length=20,
        choices=TaxRegime.choices,
        default=TaxRegime.MEI,
    )
    cnae = models.CharField("CNAE principal", max_length=10, blank=True)
    postal_code = models.CharField("CEP", max_length=9, blank=True)
    street = models.CharField("Logradouro", max_length=255, blank=True)
    street_number = models.CharField("Número", max_length=20, blank=True)
    address_complement = models.CharField("Complemento", max_length=100, blank=True)
    neighborhood = models.CharField("Bairro", max_length=100, blank=True)
    city = models.CharField("Município", max_length=100, default="Rio de Janeiro")
    state = models.CharField("UF", max_length=2, default="RJ")
    phone = models.CharField("Telefone", max_length=30, blank=True)
    email = models.EmailField("E-mail da empresa", blank=True)
    logo = models.ImageField("Logo", upload_to="company/logos/", blank=True)
    primary_color = models.CharField(
        "Cor principal",
        max_length=7,
        default="#5968E8",
        validators=[
            RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Informe uma cor hexadecimal.")
        ],
    )
    accent_color = models.CharField(
        "Cor de destaque",
        max_length=7,
        default="#36B89B",
        validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Informe uma cor hexadecimal.")],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cadastro da empresa"
        verbose_name_plural = "Cadastro da empresa"

    def __str__(self):
        return self.trade_name or self.legal_name


class SMTPConfiguration(models.Model):
    host = models.CharField("Servidor SMTP", max_length=255)
    port = models.PositiveIntegerField("Porta", default=587)
    username = models.CharField("Usuário SMTP", max_length=255)
    password_encrypted = models.BinaryField(
        "Senha SMTP criptografada",
        editable=False,
        default=bytes,
    )
    from_email = models.EmailField("E-mail remetente")
    use_tls = models.BooleanField("Usar TLS", default=True)
    use_ssl = models.BooleanField("Usar SSL", default=False)
    timeout = models.PositiveIntegerField("Timeout (segundos)", default=10)
    is_active = models.BooleanField("Ativa", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração SMTP"
        verbose_name_plural = "Configuração SMTP"

    def __str__(self):
        return f"{self.from_email} via {self.host}"


class A1Certificate(models.Model):
    encrypted_file = models.BinaryField(
        "Certificado criptografado",
        editable=False,
        default=bytes,
    )
    encrypted_password = models.BinaryField(
        "Senha criptografada",
        editable=False,
        default=bytes,
    )
    original_filename = models.CharField(max_length=255, editable=False)
    serial_number = models.CharField(max_length=100, editable=False)
    valid_until = models.DateTimeField("Válido até", editable=False)
    uploaded_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Certificado digital A1"
        verbose_name_plural = "Certificado digital A1"

    def __str__(self):
        return f"Certificado A1 válido até {self.valid_until:%d/%m/%Y}"
