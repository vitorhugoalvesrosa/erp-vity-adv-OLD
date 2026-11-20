from django.contrib.auth.models import Group, Permission
from django.db.models import Q


ADMIN_GROUP = "Administrador"
MANAGER_GROUP = "Gerente"
OPERATOR_GROUP = "Operador"
BUSINESS_APP_LABELS = {"crm", "financeiro", "produtos", "pdv"}
OPERATOR_PDV_PERMISSIONS = {
    "add_cashregister",
    "change_cashregister",
    "add_sale",
    "add_cashmovement",
}


def setup_access_groups():
    groups = {}
    for name in (ADMIN_GROUP, MANAGER_GROUP, OPERATOR_GROUP):
        groups[name], _ = Group.objects.get_or_create(name=name)

    all_permissions = Permission.objects.all()
    groups[ADMIN_GROUP].permissions.set(all_permissions)
    groups[MANAGER_GROUP].permissions.set(all_permissions)
    groups[OPERATOR_GROUP].permissions.set(
        all_permissions.filter(
            Q(
                content_type__app_label__in=BUSINESS_APP_LABELS,
                codename__startswith="view_",
            )
            | Q(
                content_type__app_label="pdv",
                codename__in=OPERATOR_PDV_PERMISSIONS,
            )
        )
    )
    return groups
