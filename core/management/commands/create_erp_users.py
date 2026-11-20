from getpass import getpass

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


USER_ROLES = {
    "admin": ADMIN_GROUP,
    "gerente": MANAGER_GROUP,
    "operador": OPERATOR_GROUP,
}


class Command(BaseCommand):
    help = (
        "Cria ou atualiza admin, gerente e operador. "
        "As senhas são solicitadas sem exibição e nunca são impressas."
    )

    def handle(self, *args, **options):
        User = get_user_model()
        user_manager = User._default_manager
        passwords = {}

        for username in USER_ROLES:
            password = getpass(f"Nova senha para {username}: ")
            confirmation = getpass(f"Confirme a senha para {username}: ")
            if password != confirmation:
                raise CommandError(f"As senhas para '{username}' não coincidem.")

            user = user_manager.filter(username=username).first() or User(
                username=username
            )
            try:
                password_validation.validate_password(password, user=user)
            except ValidationError as error:
                messages = " ".join(error.messages)
                raise CommandError(
                    f"A senha para '{username}' não atende aos requisitos: {messages}"
                ) from error
            passwords[username] = password

        with transaction.atomic():
            groups = setup_access_groups()
            for username, group_name in USER_ROLES.items():
                user, _ = user_manager.get_or_create(username=username)
                user.set_password(passwords[username])
                user.is_staff = True
                user.is_superuser = username == "admin"
                user.save()
                user.groups.set([groups[group_name]])

        self.stdout.write(
            self.style.SUCCESS(
                "Contas admin, gerente e operador configuradas. "
                "As senhas não foram exibidas."
            )
        )
