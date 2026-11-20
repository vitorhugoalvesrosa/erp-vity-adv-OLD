from django.urls import include, path
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LoginView, LogoutView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

from core.admin_site import erp_admin_site
from core.forms import ERPAuthenticationForm
from core.views import ERPPasswordResetConfirmView, ERPPasswordResetView

urlpatterns = [
    path(
        "login/",
        LoginView.as_view(
            authentication_form=ERPAuthenticationForm,
            template_name="core/login.html",
        ),
        name="login",
    ),
    path("logout/", LogoutView.as_view(), name="logout"),
    path(
        "admin/password_reset/",
        ERPPasswordResetView.as_view(),
        name="admin_password_reset",
    ),
    path(
        "admin/password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="core/auth/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        ERPPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="core/auth/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
    path("admin/", erp_admin_site.urls),
    path("", include("core.urls")),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/crm/", include("crm.urls")),
    path("api/financeiro/", include("financeiro.urls")),
    path("api/produtos/", include("produtos.urls")),
]
