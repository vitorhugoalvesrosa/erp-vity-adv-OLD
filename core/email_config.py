from dataclasses import dataclass

from django.conf import settings

from core.models import SMTPConfiguration
from core.secure_storage import decrypt_text


@dataclass(frozen=True)
class SMTPSettings:
    host: str
    port: int
    username: str
    password: str
    from_email: str
    use_tls: bool
    use_ssl: bool
    timeout: int

    @property
    def is_configured(self):
        return bool(
            self.host
            and self.port
            and self.username
            and self.password
            and self.from_email
        )


def get_smtp_settings():
    configuration = SMTPConfiguration.objects.filter(is_active=True).first()
    if configuration:
        return SMTPSettings(
            host=configuration.host,
            port=configuration.port,
            username=configuration.username,
            password=(
                decrypt_text(configuration.password_encrypted)
                if configuration.password_encrypted
                else ""
            ),
            from_email=configuration.from_email,
            use_tls=configuration.use_tls,
            use_ssl=configuration.use_ssl,
            timeout=configuration.timeout,
        )

    return SMTPSettings(
        host=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        username=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        from_email=settings.DEFAULT_FROM_EMAIL,
        use_tls=settings.EMAIL_USE_TLS,
        use_ssl=settings.EMAIL_USE_SSL,
        timeout=settings.EMAIL_TIMEOUT,
    )
