from collections import OrderedDict

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Cria o usuário administrador padrão do ERP Vity"

    def handle(self, *args, **options):
        User = get_user_model()
        username = "admin"
        password = "administrador"

        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=["password", "is_staff", "is_superuser"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"Usuário administrador já existia. A senha foi atualizada para: {password}"
                )
            )
            return

        user = User.objects.create_superuser(
            username=username,
            email="admin@erp-vity.local",
            password=password,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Usuário administrador criado com sucesso: {user.username} / {password}"
            )
        )
