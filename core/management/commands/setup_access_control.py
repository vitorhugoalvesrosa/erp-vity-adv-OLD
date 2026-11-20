from django.core.management.base import BaseCommand

from core.access_control import setup_access_groups


class Command(BaseCommand):
    help = "Cria e atualiza os grupos e permissões padrão do ERP."

    def handle(self, *args, **options):
        setup_access_groups()
        self.stdout.write(self.style.SUCCESS("Grupos e permissões do ERP atualizados."))
