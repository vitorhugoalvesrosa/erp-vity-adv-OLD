import os

from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.access_control import (
    ADMIN_GROUP,
    MANAGER_GROUP,
    OPERATOR_GROUP,
    setup_access_groups,
)
from core.models import ERPUserBootstrap


BOOTSTRAP_NAME = "default-erp-users"
USER_ROLES = {
    "admin": (ADMIN_GROUP, "ERP_BOOTSTRAP_ADMIN_PASSWORD"),
    "gerente": (MANAGER_GROUP, "ERP_BOOTSTRAP_GERENTE_PASSWORD"),
    "operador": (OPERATOR_GROUP, "ERP_BOOTSTRAP_OPERADOR_PASSWORD"),
}


class Command(BaseCommand):
    help = "Cria as contas padrão uma única vez usando senhas temporárias do ambiente."

    def handle(self, *args, **options):
        if ERPUserBootstrap.objects.filter(name=BOOTSTRAP_NAME).exists():
            self.stdout.write("Bootstrap já concluído; nenhuma conta foi alterada.")
            return

        passwords = {
            username: os.environ.get(env_var, "")
            for username, (_, env_var) in USER_ROLES.items()
        }
        configured = [bool(password) for password in passwords.values()]
        if not any(configured):
            self.stdout.write(
                "Bootstrap ignorado: variáveis temporárias de senha não configuradas."
            )
            return
        if not all(configured):
            missing = [
                env_var
                for username, (_, env_var) in USER_ROLES.items()
                if not passwords[username]
            ]
            raise CommandError(
                "Configure todas as variáveis de senha do bootstrap: "
                + ", ".join(missing)
            )

        User = get_user_model()
        for username, password in passwords.items():
            user = User._default_manager.filter(username=username).first() or User(
                username=username
            )
            try:
                password_validation.validate_password(password, user=user)
            except ValidationError as error:
                messages = " ".join(error.messages)
                raise CommandError(
                    f"A senha configurada para '{username}' não atende aos requisitos: "
                    f"{messages}"
                ) from error

        with transaction.atomic():
            _, bootstrap_started = ERPUserBootstrap.objects.get_or_create(
                name=BOOTSTRAP_NAME
            )
            if not bootstrap_started:
                self.stdout.write("Bootstrap já concluído; nenhuma conta foi alterada.")
                return

            groups = setup_access_groups()
            for username, (group_name, _) in USER_ROLES.items():
                user, _ = User._default_manager.get_or_create(username=username)
                user.set_password(passwords[username])
                user.is_staff = True
                user.is_superuser = username == "admin"
                user.save()
                user.groups.set([groups[group_name]])

        self.stdout.write(
            self.style.SUCCESS(
                "Contas admin, gerente e operador configuradas; "
                "as senhas não foram exibidas."
            )
        )
