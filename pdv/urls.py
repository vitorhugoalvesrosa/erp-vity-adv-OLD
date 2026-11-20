from django.urls import path

from . import views

app_name = "pdv"

urlpatterns = [
    path("", views.terminal, name="terminal"),
    path("caixa/abrir/", views.open_register, name="open-register"),
    path("caixa/fechar/", views.close_register, name="close-register"),
    path("caixa/movimentacao/", views.cash_movement, name="cash-movement"),
    path("vendas/rascunho/", views.create_draft, name="create-draft"),
    path("vendas/<int:pk>/finalizar/", views.finalize_sale, name="finalize-sale"),
    path("vendas/<int:pk>/cancelar/", views.cancel_draft, name="cancel-draft"),
]
