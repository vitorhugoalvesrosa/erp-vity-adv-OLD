import os
import secrets
from datetime import date
from io import BytesIO
from datetime import datetime, timedelta, timezone as datetime_timezone
from io import StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.core.mail import get_connection
from django.http import HttpResponse
from django.urls import resolve, reverse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient
from PIL import Image as PILImage

from crm.models import Conta, Proposta
from core.admin_site import ERPAdminAuthenticationForm, erp_admin_site
from core.access_control import MANAGER_GROUP, OPERATOR_GROUP, setup_access_groups
from core.configuration_forms import A1CertificateForm, CompanyProfileForm, SMTPConfigurationForm
from core.email_config import get_smtp_settings
from core.forms import ContratoForm
from core.management.commands.bootstrap_erp_users import BOOTSTRAP_NAME
from core.models import A1Certificate, CompanyProfile, ERPAdminPasswordReset, ERPUserBootstrap, SMTPConfiguration
from core.secure_storage import decrypt_bytes, decrypt_text
from core.views import (
    administration,
    company_logo,
    contract_pdf,
    generate_sale_order,
    home,
    record_delete,
    record_edit,
    record_list,
    send_notice,
)
from produtos.models import Produto
from financeiro.models import Contrato, PedidoVenda
from juridico.models import Prazo, Processo, Publicacao, Tarefa


class HomePageRouteTests(SimpleTestCase):
    def test_homepage_and_module_links_resolve(self):
        routes = {
            "home": "/",
            "admin-settings": "/administracao/",
            "visual-identity": "/administracao/identidade-visual/",
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
            "admin:core_companyprofile_changelist": "/admin/core/companyprofile/",
            "admin:core_a1certificate_changelist": "/admin/core/a1certificate/",
            "admin:core_smtpconfiguration_changelist": "/admin/core/smtpconfiguration/",
            "admin:pdv_cashregister_changelist": "/admin/pdv/cashregister/",
            "admin:pdv_sale_changelist": "/admin/pdv/sale/",
            "pdv:terminal": "/pdv/",
        }

        for name, path in routes.items():
            with self.subTest(route=name):
                self.assertEqual(reverse(name), path)

        self.assertEqual(
            reverse("generate-sale-order", args=[1]),
            "/app/orcamentos/1/gerar-pedido/",
        )
        self.assertEqual(reverse("contract-pdf", args=[1]), "/app/contratos/1/pdf/")
        self.assertEqual(
            reverse("record-list", kwargs={"module": "produtos"}),
            "/app/produtos/",
        )


class JuridicoMvpTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        groups = setup_access_groups()
        cls.manager = get_user_model().objects.create_user(
            username="juridico-manager",
            password="test-password",
            is_staff=True,
        )
        cls.manager.groups.add(groups[MANAGER_GROUP])
        cls.conta = Conta.objects.create(
            nome="Cliente Jurídico",
            documento="12345678000190",
            status=Conta.Status.CLIENTE,
        )

    def test_manager_can_create_process_via_api(self):
        client = APIClient()
        client.force_authenticate(user=self.manager)
        response = client.post(
            "/api/juridico/processos/",
            {
                "numero_cnj": "0000001-00.2026.8.19.0001",
                "titulo": "Revisão contratual",
                "cliente": self.conta.pk,
                "parte_contraria": "Empresa Exemplo",
                "tribunal": "TJRJ",
                "vara": "1ª Vara Cível",
                "area": "civel",
                "status": "ativo",
                "responsavel": self.manager.pk,
                "valor_causa": "1000.00",
                "observacoes": "",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_dashboard_counts_active_deadlines_and_publications(self):
        processo = Processo.objects.create(
            numero_cnj="0000002-00.2026.8.19.0001",
            titulo="Cobrança",
            cliente=self.conta,
            tribunal="TJRJ",
            responsavel=self.manager,
        )
        Prazo.objects.create(
            processo=processo,
            titulo="Manifestação",
            responsavel=self.manager,
            data_vencimento=date.today(),
        )
        Publicacao.objects.create(
            processo=processo,
            monitoramento="12345678000190",
            tribunal="TJRJ",
            titulo="Intimação urgente",
            conteudo="Prazo identificado",
            publicada_em=date.today(),
            urgente=True,
        )
        request = RequestFactory().get("/")
        request.user = self.manager
        response = home(request)
        self.assertEqual(response.status_code, 200)

    def test_juridical_api_supports_filters_actions_and_summaries(self):
        processo = Processo.objects.create(
            numero_cnj="0000003-00.2026.8.19.0001",
            titulo="Ação empresarial",
            cliente=self.conta,
            tribunal="TRF2",
            area=Processo.Area.EMPRESARIAL,
            status=Processo.Status.ATIVO,
            responsavel=self.manager,
        )
        tarefa = Tarefa.objects.create(
            processo=processo,
            titulo="Revisar contrato",
            responsavel=self.manager,
            prioridade=Tarefa.Prioridade.ALTA,
        )
        publicacao = Publicacao.objects.create(
            processo=processo,
            monitoramento="12345678000190",
            tribunal="TRF2",
            titulo="Intimação",
            conteudo="Publicação para análise",
            publicada_em=date.today(),
            urgente=True,
        )
        client = APIClient()
        client.force_authenticate(user=self.manager)

        process_filter = client.get(
            "/api/juridico/processos/",
            {"area": "empresarial", "status": "ativo", "search": "empresarial"},
        )
        process_summary = client.get("/api/juridico/processos/resumo/")
        task_action = client.post(f"/api/juridico/tarefas/{tarefa.pk}/concluir/")
        publication_action = client.post(
            f"/api/juridico/publicacoes/{publicacao.pk}/processar/"
        )

        self.assertEqual(process_filter.status_code, 200)
        self.assertEqual(process_summary.status_code, 200)
        self.assertTrue(
            any(row["numero_cnj"] == processo.numero_cnj for row in process_filter.data)
        )
        self.assertEqual(task_action.status_code, 200)
        self.assertEqual(task_action.data["status"], "concluida")
        self.assertEqual(publication_action.status_code, 200)
        self.assertTrue(publication_action.data["processada"])

    def test_operator_can_read_but_not_create_juridical_records(self):
        user_model = get_user_model()
        operator = user_model.objects.create_user(
            username="juridico-operator",
            password="test-password",
            is_staff=True,
        )
        operator.groups.add(setup_access_groups()[OPERATOR_GROUP])
        client = APIClient()
        client.force_authenticate(user=operator)

        list_response = client.get("/api/juridico/processos/")
        create_response = client.post(
            "/api/juridico/processos/",
            {"titulo": "Não autorizado"},
            format="json",
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(create_response.status_code, 403)


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


class SecureSystemConfigurationTests(TestCase):
    def test_company_profile_accepts_formatted_alphanumeric_cnpj(self):
        form = CompanyProfileForm(
            data={
                "legal_name": "Empresa de Teste MEI",
                "trade_name": "Loja Teste",
                "cnpj": "12.345.ABC/9012-34",
                "municipal_registration": "",
                "state_registration": "",
                "tax_regime": "mei",
                "cnae": "",
                "postal_code": "",
                "street": "",
                "street_number": "",
                "address_complement": "",
                "neighborhood": "",
                "city": "Rio de Janeiro",
                "state": "RJ",
                "phone": "",
                "email": "",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        company = form.save()
        self.assertEqual(company.cnpj, "12345ABC901234")

    @override_settings(CONFIG_ENCRYPTION_KEY="")
    def test_smtp_password_requires_environment_encryption_key(self):
        form = SMTPConfigurationForm(
            data={
                "host": "smtp.example.com",
                "port": "587",
                "username": "erp@example.com",
                "smtp_password": "not-stored",
                "from_email": "erp@example.com",
                "use_tls": "on",
                "timeout": "10",
                "is_active": "on",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("CONFIG_ENCRYPTION_KEY", str(form.errors))
        self.assertEqual(SMTPConfiguration.objects.count(), 0)

    def test_smtp_configuration_encrypts_password_and_drives_mail_backend(self):
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode("ascii")
        with override_settings(
            CONFIG_ENCRYPTION_KEY=key,
            EMAIL_BACKEND="core.mail_backend.ConfiguredSMTPEmailBackend",
        ):
            form = SMTPConfigurationForm(
                data={
                    "host": "smtp.example.com",
                    "port": "587",
                    "username": "erp@example.com",
                    "smtp_password": "smtp-secret",
                    "from_email": "erp@example.com",
                    "use_tls": "on",
                    "timeout": "10",
                    "is_active": "on",
                }
            )
            self.assertTrue(form.is_valid(), form.errors)
            configuration = form.save()

            self.assertNotIn(
                b"smtp-secret",
                bytes(configuration.password_encrypted),
            )
            self.assertEqual(
                decrypt_text(configuration.password_encrypted),
                "smtp-secret",
            )
            resolved = get_smtp_settings()
            self.assertTrue(resolved.is_configured)
            self.assertEqual(resolved.from_email, "erp@example.com")
            backend = get_connection()
            self.assertEqual(backend.host, "smtp.example.com")
            self.assertEqual(backend.password, "smtp-secret")

    def test_a1_upload_is_validated_and_encrypted_in_database(self):
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode("ascii")
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = datetime.now(datetime_timezone.utc)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ERP Test")])
        certificate = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=30))
            .sign(private_key, hashes.SHA256())
        )
        certificate_bytes = pkcs12.serialize_key_and_certificates(
            b"erp-test",
            private_key,
            certificate,
            None,
            serialization.BestAvailableEncryption(b"certificate-secret"),
        )

        with override_settings(CONFIG_ENCRYPTION_KEY=key):
            form = A1CertificateForm(
                data={"certificate_password": "certificate-secret"},
                files={
                    "certificate_file": SimpleUploadedFile(
                        "empresa.p12",
                        certificate_bytes,
                    )
                },
            )
            self.assertTrue(form.is_valid(), form.errors)
            saved_certificate = form.save()

            self.assertNotIn(
                certificate_bytes,
                bytes(saved_certificate.encrypted_file),
            )
            self.assertEqual(
                decrypt_bytes(saved_certificate.encrypted_file),
                certificate_bytes,
            )
            self.assertEqual(
                decrypt_text(saved_certificate.encrypted_password),
                "certificate-secret",
            )
            self.assertEqual(A1Certificate.objects.count(), 1)


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
    EMAIL_HOST_USER="erp@example.com",
    EMAIL_HOST_PASSWORD="smtp-test-secret",
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


class ContractWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.manager = user_model.objects.create_user(
            username="contract-manager",
            password="test-password",
            is_staff=True,
        )
        cls.manager.groups.add(setup_access_groups()[MANAGER_GROUP])

    def setUp(self):
        self.client.force_login(self.manager)
        account = Conta.objects.create(
            nome="Cliente de serviços",
            documento="12345678901",
        )
        self.proposal = Proposta.objects.create(
            conta=account,
            valor_total="2500.00",
            status=Proposta.Status.RASCUNHO,
            data_validade=date(2026, 12, 31),
        )

    def test_approved_budget_generates_a_sale_order(self):
        self.proposal.status = Proposta.Status.GANHA
        self.proposal.save(update_fields=["status"])

        response = self.client.post(
            reverse("generate-sale-order", args=[self.proposal.pk])
        )

        self.assertRedirects(response, reverse("record-list", args=["pedidos"]))
        order = PedidoVenda.objects.get(proposta=self.proposal)
        self.assertEqual(str(order.valor_final), self.proposal.valor_total)
        self.assertEqual(order.data_faturamento, self.proposal.data_validade)

    def test_unapproved_budget_cannot_generate_a_sale_order(self):
        response = self.client.post(
            reverse("generate-sale-order", args=[self.proposal.pk])
        )

        self.assertRedirects(response, reverse("record-list", args=["propostas"]))
        self.assertFalse(PedidoVenda.objects.filter(proposta=self.proposal).exists())

    def test_contract_form_and_pdf_are_bound_to_the_approved_order(self):
        self.proposal.status = Proposta.Status.GANHA
        self.proposal.save(update_fields=["status"])
        order = PedidoVenda.objects.get(proposta=self.proposal)
        form = ContratoForm()
        self.assertQuerySetEqual(form.fields["pedido_venda"].queryset, [order])
        contract = Contrato.objects.create(
            pedido_venda=order,
            service_description="Manutenção preventiva mensal do sistema.",
            payment_terms="5 parcelas mensais de R$ 500,00.",
        )
        self.assertFalse(ContratoForm().fields["pedido_venda"].queryset.exists())

        response = self.client.get(reverse("contract-pdf", args=[contract.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))

    def test_company_logo_and_colors_are_applied_to_the_system(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            image_data = BytesIO()
            PILImage.new("RGB", (20, 20), color="red").save(image_data, format="PNG")
            form = CompanyProfileForm(
                data={
                    "legal_name": "Prestadora de Serviços Ltda.",
                    "trade_name": "Serviços Vity",
                    "cnpj": "12345678901234",
                    "tax_regime": CompanyProfile.TaxRegime.SIMPLES,
                    "city": "São Paulo",
                    "state": "SP",
                    "primary_color": "#123456",
                    "sidebar_color": "#234567",
                    "accent_color": "#298765",
                },
                files={
                    "logo": SimpleUploadedFile(
                        "marca.png", image_data.getvalue(), content_type="image/png"
                    )
                },
            )
            self.assertTrue(form.is_valid(), form.errors)
            form.save()

            dashboard = self.client.get(reverse("home"))
            logo = self.client.get(reverse("company-logo"))

        self.assertContains(dashboard, "--blue: #123456")
        self.assertContains(dashboard, "--navy: #234567")
        self.assertContains(dashboard, "Serviços Vity")
        self.assertEqual(logo.status_code, 200)
        self.assertEqual(logo["Content-Type"], "image/png")

    def test_visual_identity_settings_and_admin_branding(self):
        self.client.force_login(self.manager)
        denied = self.client.get(reverse("visual-identity"))
        self.assertEqual(denied.status_code, 403)

        admin_user = get_user_model().objects.create_superuser(
            username="branding-admin",
            password="test-password",
        )
        self.client.force_login(admin_user)
        page = self.client.get(reverse("visual-identity"))
        self.assertContains(page, "Cor do menu lateral")
        self.assertContains(page, "branding-preview")

        response = self.client.post(
            reverse("visual-identity"),
            {
                "legal_name": "Prestadora de Serviços Ltda.",
                "trade_name": "Marca Configurada",
                "cnpj": "12345678901234",
                "primary_color": "#123456",
                "sidebar_color": "#234567",
                "accent_color": "#298765",
            },
        )

        self.assertRedirects(response, reverse("visual-identity"))
        profile = CompanyProfile.objects.get()
        self.assertEqual(profile.sidebar_color, "#234567")
        self.assertContains(self.client.get(reverse("home")), "--navy: #234567")

        admin_page = self.client.get(reverse("admin:index"))
        self.assertContains(admin_page, "Marca Configurada")
        self.assertContains(admin_page, "Administração e cadastros")
        self.assertContains(admin_page, "core/admin.css")
        self.assertContains(admin_page, "--erp-admin-sidebar: #234567")


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
        self.assertIn('data-menu-group="crm"', dashboard.content.decode())
        self.assertIn("Orçamentos", dashboard.content.decode())
        self.assertIn('id="icon-overview"', dashboard.content.decode())
        self.assertIn('aria-controls="nav-finance"', dashboard.content.decode())
        self.assertIn(
            'href="/pdv/" target="_blank" rel="noopener"',
            dashboard.content.decode(),
        )
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
        self.assertIn("Dados da empresa", content)
        self.assertIn("Certificado A1", content)
        self.assertIn("Configuração SMTP", content)
        self.assertIn("Operação do PDV", content)

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
