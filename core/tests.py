import os
import secrets
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.http import HttpResponse
from django.urls import resolve, reverse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from crm.models import Conta
from core.admin_site import ERPAdminAuthenticationForm, erp_admin_site
from core.access_control import MANAGER_GROUP, OPERATOR_GROUP, setup_access_groups
from core.management.commands.bootstrap_erp_users import BOOTSTRAP_NAME
from core.models import ERPAdminPasswordReset, ERPUserBootstrap
from core.views import (
    administration,
    home,
    record_delete,
    record_edit,
    record_list,
    send_notice,
)
from produtos.models import Produto


class HomePageRouteTests(SimpleTestCase):
    def test_homepage_and_module_links_resolve(self):
        routes = {
            "home": "/",
            "admin-settings": "/administracao/",
            "login": "/login/",
            "admin:login": "/admin/login/",
            "admin_password_reset": "/admin/password_reset/",
            "send-email-notice": "/emails/enviar/",
            "admin:crm_conta_changelist": "/admin/crm/conta/",
            "admin:crm_proposta_changelist": "/admin/crm/proposta/",
            "admin:produtos_produto_changelist": "/admin/produtos/produto/",
            "admin:financeiro_pedidovenda_changelist": "/admin/financeiro/pedidovenda/",
            "admin:financeiro_contareceber_changelist": "/admin/financeiro/contareceber/",
            "admin:financeiro_pagamento_changelist": "/admin/financeiro/pagamento/",
        }

        for name, path in routes.items():
            with self.subTest(route=name):
                self.assertEqual(reverse(name), path)

        self.assertEqual(
            reverse("record-list", kwargs={"module": "produtos"}),
            "/app/produtos/",
        )


class ApiRolePermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        groups = setup_access_groups()
        user_model = get_user_model()
        cls.operator = user_model.objects.create_user(
            username="operator-test",
            password="test-password",
            is_staff=True,
        )
        cls.operator.groups.add(groups[OPERATOR_GROUP])
        cls.manager = user_model.objects.create_user(
            username="manager-test",
            password="test-password",
            is_staff=True,
        )
        cls.manager.groups.add(groups[MANAGER_GROUP])
        cls.product = Produto.objects.create(
            nome="Produto de teste",
            sku="TEST-001",
            preco="10.00",
        )

    def setUp(self):
        self.client = APIClient()

    def test_operator_can_read_but_cannot_write_products(self):
        self.client.force_authenticate(user=self.operator)

        list_response = self.client.get("/api/produtos/")
        create_response = self.client.post(
            "/api/produtos/",
            {"nome": "Novo", "sku": "TEST-002", "preco": "5.00"},
            format="json",
        )
        delete_response = self.client.delete(f"/api/produtos/{self.product.pk}/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)

    def test_manager_can_create_products(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            "/api/produtos/",
            {"nome": "Novo", "sku": "TEST-003", "preco": "5.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)

    def test_service_products_do_not_track_stock(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            "/api/produtos/",
            {
                "nome": "Consultoria",
                "sku": "SERVICE-001",
                "preco": "120.00",
                "eh_servico": True,
                "quantidade_estoque": 5,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["eh_servico"])
        self.assertEqual(response.data["quantidade_estoque"], 0)

    def test_operator_cannot_access_django_admin(self):
        request = RequestFactory().get("/admin/")
        request.user = self.operator

        self.assertFalse(erp_admin_site.has_permission(request))


class ProductServiceInventoryTests(TestCase):
    def test_service_stock_is_zero_after_partial_update(self):
        product = Produto.objects.create(
            nome="Produto conversível",
            sku="SERVICE-PARTIAL-001",
            preco="10.00",
            quantidade_estoque=7,
        )

        product.eh_servico = True
        product.save(update_fields=["eh_servico"])
        product.refresh_from_db()

        self.assertEqual(product.quantidade_estoque, 0)


class ERPUserBootstrapTests(TestCase):
    def test_bootstrap_creates_users_once_without_resetting_them(self):
        env_passwords = {
            "ERP_BOOTSTRAP_ADMIN_PASSWORD": secrets.token_urlsafe(32),
            "ERP_BOOTSTRAP_GERENTE_PASSWORD": secrets.token_urlsafe(32),
            "ERP_BOOTSTRAP_OPERADOR_PASSWORD": secrets.token_urlsafe(32),
        }

        with patch.dict(os.environ, env_passwords):
            call_command("bootstrap_erp_users", stdout=StringIO())

        user_model = get_user_model()
        admin = user_model.objects.get(username="admin")
        manager = user_model.objects.get(username="gerente")
        operator = user_model.objects.get(username="operador")

        self.assertTrue(admin.is_superuser)
        self.assertFalse(manager.is_superuser)
        self.assertTrue(manager.is_staff)
        self.assertTrue(operator.is_staff)
        self.assertTrue(
            admin.check_password(env_passwords["ERP_BOOTSTRAP_ADMIN_PASSWORD"])
        )
        self.assertEqual(ERPUserBootstrap.objects.count(), 1)

        changed_passwords = {key: secrets.token_urlsafe(32) for key in env_passwords}
        with patch.dict(os.environ, changed_passwords):
            call_command("bootstrap_erp_users", stdout=StringIO())

        admin.refresh_from_db()
        self.assertTrue(
            admin.check_password(env_passwords["ERP_BOOTSTRAP_ADMIN_PASSWORD"])
        )


class ERPAdminPasswordResetTests(TestCase):
    def test_password_reset_token_is_one_time_and_activates_admin(self):
        user_model = get_user_model()
        admin = user_model.objects.create_user(
            username="admin",
            password=secrets.token_urlsafe(32),
            is_active=False,
        )
        ERPUserBootstrap.objects.create(name=BOOTSTRAP_NAME)

        password = secrets.token_urlsafe(32)
        reset_token = secrets.token_urlsafe(32)
        env = {
            "ERP_BOOTSTRAP_ADMIN_PASSWORD": password,
            "ERP_ADMIN_PASSWORD_RESET_TOKEN": reset_token,
        }
        with patch.dict(os.environ, env):
            call_command("bootstrap_erp_users", stdout=StringIO())

        admin.refresh_from_db()
        self.assertTrue(admin.is_active)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password(password))
        self.assertEqual(ERPAdminPasswordReset.objects.count(), 1)

        with patch.dict(
            os.environ,
            {
                **env,
                "ERP_BOOTSTRAP_ADMIN_PASSWORD": secrets.token_urlsafe(32),
            },
        ):
            call_command("bootstrap_erp_users", stdout=StringIO())

        admin.refresh_from_db()
        self.assertTrue(admin.check_password(password))


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST="smtp.example.com",
    DEFAULT_FROM_EMAIL="erp@example.com",
)
class EmailModuleTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin_user = user_model.objects.create_superuser(
            username="mail-admin",
            email="admin@example.com",
            password="test-password",
        )
        self.recipient = user_model.objects.create_user(
            username="mail-recipient",
            email="recipient@example.com",
            password="test-password",
        )

    def test_password_reset_request_sends_one_time_link(self):
        form = PasswordResetForm(data={"email": self.recipient.email})
        self.assertTrue(form.is_valid())
        form.save(
            domain_override="testserver",
            subject_template_name="core/auth/password_reset_subject.txt",
            email_template_name="core/auth/password_reset_email.html",
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.recipient.email])
        self.assertIn("/reset/", mail.outbox[0].body)

    def test_admin_can_send_notice_without_exposing_recipient_addresses(self):
        request = RequestFactory().post(
            reverse("send-email-notice"),
            {
                "recipients": [str(self.recipient.pk)],
                "subject": "Informação importante",
                "message": "Atualização do ERP.",
            },
        )
        request.user = self.admin_user
        with patch(
            "core.views.render",
            side_effect=lambda request, template, context: HttpResponse(
                str(context["form"].errors)
            ),
        ) as render:
            with patch("core.views.messages.success"):
                response = send_notice(request)

        self.assertFalse(render.called, response.content.decode())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("send-email-notice"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["erp@example.com"])
        self.assertEqual(mail.outbox[0].bcc, [self.recipient.email])
        self.assertEqual(mail.outbox[0].body, "Atualização do ERP.")

    def test_operator_cannot_send_notices(self):
        operator = get_user_model().objects.create_user(
            username="mail-operator",
            email="operator@example.com",
            password="test-password",
            is_staff=True,
        )
        operator.groups.add(setup_access_groups()[OPERATOR_GROUP])
        self.client.force_login(operator)

        response = self.client.get(reverse("send-email-notice"))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(mail.outbox, [])


class FrontendPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        groups = setup_access_groups()
        user_model = get_user_model()
        cls.manager = user_model.objects.create_user(
            username="frontend-manager",
            password="test-password",
            is_staff=True,
        )
        cls.manager.groups.add(groups[MANAGER_GROUP])
        cls.operator = user_model.objects.create_user(
            username="frontend-operator",
            password="test-password",
            is_staff=True,
        )
        cls.operator.groups.add(groups[OPERATOR_GROUP])
        cls.admin_user = user_model.objects.create_superuser(
            username="frontend-admin",
            password="test-password",
        )

    def request_as(self, path, user, data=None):
        factory = RequestFactory()
        request = factory.post(path, data) if data is not None else factory.get(path)
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_anonymous_home_redirects_to_custom_login(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/login/?next=/")

    def test_custom_login_and_password_reset_pages_render(self):
        login_request = self.request_as("/login/", AnonymousUser())
        login_page = resolve("/login/").func(login_request)
        reset_request = self.request_as(
            "/admin/password_reset/",
            AnonymousUser(),
        )
        reset_page = resolve("/admin/password_reset/").func(reset_request)

        login_page.render()
        reset_page.render()
        self.assertEqual(login_page.status_code, 200)
        self.assertIn("Acesse sua conta", login_page.content.decode())
        self.assertIn("/static/core/app.css", login_page.content.decode())
        self.assertEqual(reset_page.status_code, 200)
        self.assertIn("Redefinir senha", reset_page.content.decode())

    def test_dashboard_and_module_list_render(self):
        Produto.objects.create(
            nome="Produto no painel",
            sku="PANEL-001",
            preco="14.50",
            quantidade_estoque=3,
        )
        Produto.objects.create(
            nome="Serviço no painel",
            sku="PANEL-SERVICE-001",
            preco="14.50",
            eh_servico=True,
            quantidade_estoque=3,
        )

        dashboard = home(self.request_as("/", self.manager))
        product_list = record_list(
            self.request_as("/app/produtos/", self.operator),
            module="produtos",
        )

        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("Visão geral", dashboard.content.decode())
        self.assertIn('id="menu-toggle"', dashboard.content.decode())
        self.assertNotIn("Administração", dashboard.content.decode())
        self.assertEqual(product_list.status_code, 200)
        self.assertIn("Produto no painel", product_list.content.decode())
        self.assertIn("Serviço", product_list.content.decode())
        self.assertIn("Não controlado", product_list.content.decode())

    def test_record_form_and_delete_confirmation_render(self):
        product = Produto.objects.create(
            nome="Produto removível",
            sku="DELETE-001",
            preco="14.50",
        )
        form_page = record_edit(
            self.request_as("/app/produtos/novo/", self.manager),
            module="produtos",
        )
        delete_page = record_delete(
            self.request_as(
                f"/app/produtos/{product.pk}/excluir/",
                self.manager,
            ),
            module="produtos",
            pk=product.pk,
        )

        self.assertEqual(form_page.status_code, 200)
        self.assertIn("Novo produto", form_page.content.decode())
        self.assertIn('id="id_eh_servico"', form_page.content.decode())
        self.assertIn('id="field-row-quantidade_estoque"', form_page.content.decode())
        self.assertEqual(delete_page.status_code, 200)

    def test_service_product_form_does_not_save_stock_quantity(self):
        request = self.request_as(
            "/app/produtos/novo/",
            self.manager,
            {
                "nome": "Consultoria",
                "descricao": "",
                "sku": "SERVICE-FORM-001",
                "preco": "120.00",
                "eh_servico": "on",
                "quantidade_estoque": "5",
                "ativo": "on",
            },
        )

        response = record_edit(request, module="produtos")

        self.assertEqual(response.status_code, 302)
        service = Produto.objects.get(sku="SERVICE-FORM-001")
        self.assertTrue(service.eh_servico)
        self.assertEqual(service.quantidade_estoque, 0)

    def test_manager_can_render_email_module(self):
        response = send_notice(
            self.request_as("/emails/enviar/", self.manager),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Enviar comunicado", response.content.decode())

    def test_only_superuser_can_render_administration_settings(self):
        manager_request = self.request_as("/administracao/", self.manager)
        with self.assertRaises(PermissionDenied):
            administration(manager_request)

        admin_page = administration(
            self.request_as("/administracao/", self.admin_user),
        )

        self.assertEqual(admin_page.status_code, 200)
        content = admin_page.content.decode()
        self.assertIn("Acessos e permissões", content)
        self.assertIn("Grupos e permissões", content)
        self.assertIn("Financeiro", content)
        self.assertIn("Django Admin", content)

    def test_only_superusers_can_open_django_admin(self):
        request = RequestFactory().get("/admin/")
        request.user = self.manager
        self.assertFalse(erp_admin_site.has_permission(request))

        request.user = self.admin_user
        self.assertTrue(erp_admin_site.has_permission(request))

    def test_manager_is_redirected_away_from_admin(self):
        self.client.force_login(self.manager)

        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/admin/login/?next=/admin/")

    def test_admin_login_form_rejects_non_superusers(self):
        form = ERPAdminAuthenticationForm(
            data={
                "username": self.manager.username,
                "password": "test-password",
            }
        )

        self.assertFalse(form.is_valid())

    def test_operator_cannot_create_business_records(self):
        request = RequestFactory().post(
            "/app/contas/novo/",
            {
                "nome": "Conta bloqueada",
                "documento": "123456789",
                "email": "",
                "telefone": "",
                "status": "lead",
            },
        )
        request.user = self.operator

        with self.assertRaises(PermissionDenied):
            record_edit(request, module="contas")

    def test_manager_can_create_business_records(self):
        request = RequestFactory().post(
            "/app/contas/novo/",
            {
                "nome": "Conta de teste",
                "documento": "987654321",
                "email": "cliente@example.com",
                "telefone": "11999999999",
                "status": "lead",
            },
        )
        request.user = self.manager

        with patch("core.views.messages.success"):
            response = record_edit(request, module="contas")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Conta.objects.filter(nome="Conta de teste").exists())
