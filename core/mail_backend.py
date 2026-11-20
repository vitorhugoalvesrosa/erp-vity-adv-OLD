from django.core.mail.backends.smtp import EmailBackend

from core.email_config import get_smtp_settings


class ConfiguredSMTPEmailBackend(EmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        configuration = get_smtp_settings()
        kwargs.setdefault("host", configuration.host)
        kwargs.setdefault("port", configuration.port)
        kwargs.setdefault("username", configuration.username)
        kwargs.setdefault("password", configuration.password)
        kwargs.setdefault("use_tls", configuration.use_tls)
        kwargs.setdefault("use_ssl", configuration.use_ssl)
        kwargs.setdefault("timeout", configuration.timeout)
        super().__init__(fail_silently=fail_silently, **kwargs)
