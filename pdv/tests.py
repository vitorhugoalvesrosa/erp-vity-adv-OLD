from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import RequestFactory, TestCase

from core.access_control import MANAGER_GROUP, OPERATOR_GROUP, setup_access_groups
from produtos.models import Produto

from .models import CashMovement, CashRegister, Sale, SaleTender
from .services import (
    POSWorkflowError,
    cancel_draft_sale,
    close_register,
    complete_sale,
    create_draft_sale,
    expected_cash,
    open_register,
    record_cash_movement,
)
from .views import terminal


class POSWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        groups = setup_access_groups()
        user_model = get_user_model()
        cls.operator = user_model.objects.create_user(
            username="pdv-operator",
            password="test-password",
            is_staff=True,
        )
        cls.operator.groups.add(groups[OPERATOR_GROUP])
        cls.manager = user_model.objects.create_user(
            username="pdv-manager",
            password="test-password",
            is_staff=True,
        )
        cls.manager.groups.add(groups[MANAGER_GROUP])
        cls.product = Produto.objects.create(
            nome="Caderno",
            sku="SKU-CADERNO",
            preco="15.00",
            quantidade_estoque=5,
        )
        cls.service = Produto.objects.create(
            nome="Consultoria",
            sku="SKU-CONSULTORIA",
            preco="100.00",
            eh_servico=True,
            quantidade_estoque=10,
        )

    def test_operator_permissions_allow_pos_workflow(self):
        self.assertTrue(self.operator.has_perm("pdv.view_sale"))
        self.assertTrue(self.operator.has_perm("pdv.add_sale"))
        self.assertTrue(self.operator.has_perm("pdv.add_cashregister"))
        self.assertTrue(self.operator.has_perm("pdv.change_cashregister"))
        self.assertFalse(self.operator.has_perm("pdv.delete_sale"))

    def test_cash_register_tracks_supply_withdrawal_and_count(self):
        register = open_register(self.operator, "100.00")
        record_cash_movement(
            register,
            self.operator,
            CashMovement.Direction.IN,
            "30.00",
            "Troco",
        )
        record_cash_movement(
            register,
            self.operator,
            CashMovement.Direction.OUT,
            "10.00",
            "Retirada",
        )

        self.assertEqual(expected_cash(register), Decimal("120.00"))
        closed = close_register(register, "119.00")

        self.assertFalse(closed.is_open)
        self.assertEqual(closed.expected_amount, Decimal("120.00"))
        self.assertEqual(closed.counted_amount, Decimal("119.00"))

    def test_mixed_draft_supports_split_payments_without_stock_or_cash_changes(self):
        register = open_register(self.operator, "50.00")
        sale = create_draft_sale(
            register=register,
            cashier=self.operator,
            lines=[
                {"sku": self.product.sku, "quantity": "2"},
                {"sku": self.service.sku, "quantity": "1.5"},
            ],
            tenders=[
                {"method": SaleTender.Method.CASH, "amount": "20.00"},
                {"method": SaleTender.Method.PIX, "amount": "150.00"},
            ],
            discount_amount="10.00",
        )

        self.product.refresh_from_db()
        self.service.refresh_from_db()
        register.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.DRAFT)
        self.assertEqual(sale.subtotal, Decimal("180.00"))
        self.assertEqual(sale.total, Decimal("170.00"))
        self.assertEqual(sale.tenders.count(), 2)
        self.assertEqual(self.product.quantidade_estoque, 5)
        self.assertEqual(self.service.quantidade_estoque, 0)
        self.assertEqual(expected_cash(register), Decimal("50.00"))
        self.assertEqual(register.movements.count(), 0)

    def test_finalize_endpoint_records_sale_without_fiscal_configuration(self):
        register = open_register(self.operator, "20.00")
        sale = create_draft_sale(
            register=register,
            cashier=self.operator,
            lines=[{"sku": self.product.sku, "quantity": "1"}],
            tenders=[{"method": SaleTender.Method.CASH, "amount": "15.00"}],
            discount_amount="0.00",
        )
        self.client.force_login(self.operator)

        response = self.client.post(
            reverse("pdv:finalize-sale", kwargs={"pk": sale.pk}),
        )

        sale.refresh_from_db()
        self.product.refresh_from_db()
        register.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(sale.status, Sale.Status.COMPLETED)
        self.assertEqual(sale.fiscal_status, Sale.FiscalStatus.PENDING)
        self.assertEqual(self.product.quantidade_estoque, 4)
        self.assertEqual(register.movements.count(), 1)
        self.assertEqual(register.movements.get().kind, CashMovement.Kind.SALE)
        self.assertEqual(expected_cash(register), Decimal("35.00"))

    def test_completed_mixed_sale_updates_stock_and_records_only_cash_tender(self):
        register = open_register(self.operator, "50.00")
        sale = create_draft_sale(
            register=register,
            cashier=self.operator,
            lines=[
                {"sku": self.product.sku, "quantity": "2"},
                {"sku": self.service.sku, "quantity": "1.5"},
            ],
            tenders=[
                {"method": SaleTender.Method.CASH, "amount": "20.00"},
                {"method": SaleTender.Method.PIX, "amount": "150.00"},
            ],
            discount_amount="10.00",
        )

        complete_sale(sale, self.operator)

        self.product.refresh_from_db()
        self.service.refresh_from_db()
        self.assertEqual(self.product.quantidade_estoque, 3)
        self.assertEqual(self.service.quantidade_estoque, 0)
        self.assertEqual(expected_cash(register), Decimal("70.00"))
        self.assertEqual(register.movements.count(), 1)
        self.assertEqual(register.movements.get().amount, Decimal("20.00"))

    def test_completion_rechecks_stock_and_rolls_back_if_inventory_changed(self):
        register = open_register(self.operator, "20.00")
        sale = create_draft_sale(
            register=register,
            cashier=self.operator,
            lines=[{"sku": self.product.sku, "quantity": "1"}],
            tenders=[{"method": SaleTender.Method.CASH, "amount": "15.00"}],
            discount_amount="0.00",
        )
        self.product.quantidade_estoque = 0
        self.product.save(update_fields=("quantidade_estoque",))

        with self.assertRaisesMessage(POSWorkflowError, "Estoque insuficiente"):
            complete_sale(sale, self.operator)

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.DRAFT)
        self.assertEqual(sale.fiscal_status, Sale.FiscalStatus.NOT_STARTED)
        self.assertEqual(register.movements.count(), 0)

    def test_stock_shortage_rejects_draft_without_creating_sale(self):
        register = open_register(self.operator, "0.00")

        with self.assertRaisesMessage(POSWorkflowError, "Estoque insuficiente"):
            create_draft_sale(
                register=register,
                cashier=self.operator,
                lines=[{"sku": self.product.sku, "quantity": "6"}],
                tenders=[{"method": SaleTender.Method.CASH, "amount": "90.00"}],
                discount_amount="0.00",
            )

        self.assertEqual(Sale.objects.count(), 0)

    def test_invalid_json_rows_are_rejected_without_server_error(self):
        register = open_register(self.operator, "0.00")

        with self.assertRaisesMessage(POSWorkflowError, "itens da venda são inválidos"):
            create_draft_sale(
                register=register,
                cashier=self.operator,
                lines=[None],
                tenders=[],
                discount_amount="0.00",
            )

        with self.assertRaisesMessage(
            POSWorkflowError,
            "formas de pagamento são inválidas",
        ):
            create_draft_sale(
                register=register,
                cashier=self.operator,
                lines=[{"sku": self.product.sku, "quantity": "1"}],
                tenders=[None],
                discount_amount="0.00",
            )

        self.assertEqual(Sale.objects.count(), 0)

    def test_draft_must_be_cancelled_before_cash_can_close(self):
        register = open_register(self.operator, "0.00")
        sale = create_draft_sale(
            register=register,
            cashier=self.operator,
            lines=[{"sku": self.product.sku, "quantity": "1"}],
            tenders=[{"method": SaleTender.Method.PIX, "amount": "15.00"}],
            discount_amount="0.00",
        )

        with self.assertRaisesMessage(POSWorkflowError, "rascunhos"):
            close_register(register, "0.00")

        cancel_draft_sale(sale, self.operator, "Não prosseguir")
        closed = close_register(register, "0.00")
        self.assertFalse(closed.is_open)

    def test_terminal_requires_permission_and_renders_for_operator(self):
        request = RequestFactory().get(reverse("pdv:terminal"))
        request.user = self.operator
        response = terminal(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Ponto de venda", response.content.decode())
        self.assertIn("PDV disponível sem emissão fiscal", response.content.decode())
        self.assertNotIn("nav-workspace", response.content.decode())
        self.assertIn("Abrir caixa", response.content.decode())

    def test_terminal_renders_catalog_and_checkout_after_register_open(self):
        open_register(self.operator, "25.00")
        request = RequestFactory().get(reverse("pdv:terminal"))
        request.user = self.operator

        response = terminal(request)
        content = response.content.decode()

        self.assertIn(self.product.sku, content)
        self.assertIn("SKU-CONSULTORIA", content)
        self.assertIn("Formas de pagamento", content)
        self.assertIn("Salvar pré-venda", content)
        self.assertIn("Vendas recentes", content)

    def test_anonymous_user_is_redirected_from_terminal(self):
        response = self.client.get(reverse("pdv:terminal"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)
