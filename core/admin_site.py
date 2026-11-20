from django.contrib.admin import AdminSite
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError


class ERPAdminAuthenticationForm(AdminAuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_superuser:
            raise ValidationError("Apenas o administrador pode acessar esta área.")


class ERPAdminSite(AdminSite):
    site_header = "ERP Vity · Administração"
    site_title = "ERP Vity"
    index_title = "Configurações do sistema"
    login_form = ERPAdminAuthenticationForm

    def has_permission(self, request):
        return (
            request.user.is_active
            and request.user.is_staff
            and request.user.is_superuser
        )


erp_admin_site = ERPAdminSite(name="admin")
erp_admin_site.register(get_user_model(), UserAdmin)
erp_admin_site.register(Group, GroupAdmin)
