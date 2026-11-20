import os
import secrets
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from core.access_control import MANAGER_GROUP, OPERATOR_GROUP, setup_access_groups
from core.management.commands.bootstrap_erp_users import BOOTSTRAP_NAME
from core.models import ERPAdminPasswordReset, ERPUserBootstrap
from produtos.models import Produto


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
