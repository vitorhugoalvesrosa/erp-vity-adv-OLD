from hashlib import sha256
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
from core.models import ERPAdminPasswordReset, ERPUserBootstrap


BOOTSTRAP_NAME = "default-erp-users"
USER_ROLES = {
    "admin": (ADMIN_GROUP, "ERP_BOOTSTRAP_ADMIN_PASSWORD"),
    "gerente": (MANAGER_GROUP, "ERP_BOOTSTRAP_GERENTE_PASSWORD"),
    "operador": (OPERATOR_GROUP, "ERP_BOOTSTRAP_OPERADOR_PASSWORD"),
}
ADMIN_RESET_TOKEN_ENV = "ERP_ADMIN_PASSWORD_RESET_TOKEN"


class Command(BaseCommand):
    help = "Cria as contas padrão uma única vez usando senhas temporárias do ambiente."

    def handle(self, *args, **options):
        bootstrap_state = ERPUserBootstrap.objects.filter(name=BOOTSTRAP_NAME).first()
        if bootstrap_state:
            reset_token = os.environ.get(ADMIN_RESET_TOKEN_ENV, "")
            if reset_token:
                self.reset_admin_password(reset_token)
                return
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
                user.is_active = True
                user.save()
                user.groups.set([groups[group_name]])

        self.stdout.write(
            self.style.SUCCESS(
                "Contas admin, gerente e operador configuradas; "
                "as senhas não foram exibidas."
            )
        )

    def reset_admin_password(self, reset_token):
        if len(reset_token) < 32:
            raise CommandError(
                f"{ADMIN_RESET_TOKEN_ENV} deve ter pelo menos 32 caracteres."
            )

        password = os.environ.get(USER_ROLES["admin"][1], "")
        if not password:
            raise CommandError(
                f"Configure também {USER_ROLES['admin'][1]} para redefinir o admin."
            )

        token_hash = sha256(reset_token.encode("utf-8")).hexdigest()
        if ERPAdminPasswordReset.objects.filter(token_hash=token_hash).exists():
            self.stdout.write("Este token de redefinição já foi usado.")
            return

        User = get_user_model()
        admin = User._default_manager.filter(username="admin").first() or User(
            username="admin"
        )
        try:
            password_validation.validate_password(password, user=admin)
        except ValidationError as error:
            messages = " ".join(error.messages)
            raise CommandError(
                f"A senha configurada para 'admin' não atende aos requisitos: "
                f"{messages}"
            ) from error

        with transaction.atomic():
            _, reset_started = ERPAdminPasswordReset.objects.get_or_create(
                token_hash=token_hash
            )
            if not reset_started:
                self.stdout.write("Este token de redefinição já foi usado.")
                return

            ERPUserBootstrap.objects.select_for_update().get(name=BOOTSTRAP_NAME)

            groups = setup_access_groups()
            admin, _ = User._default_manager.get_or_create(username="admin")
            admin.set_password(password)
            admin.is_active = True
            admin.is_staff = True
            admin.is_superuser = True
            admin.save()
            admin.groups.set([groups[ADMIN_GROUP]])

        self.stdout.write(
            self.style.SUCCESS("Senha de admin redefinida com sucesso.")
        )
