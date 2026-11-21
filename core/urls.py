from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("administracao/", views.administration, name="admin-settings"),
    path(
        "administracao/identidade-visual/",
        views.visual_identity,
        name="visual-identity",
    ),
    path("identidade/logo/", views.company_logo, name="company-logo"),
    path(
        "app/orcamentos/<int:proposal_id>/gerar-pedido/",
        views.generate_sale_order,
        name="generate-sale-order",
    ),
    path(
        "app/contratos/<int:pk>/pdf/",
        views.contract_pdf,
        name="contract-pdf",
    ),
    path("app/<slug:module>/", views.record_list, name="record-list"),
    path("app/<slug:module>/novo/", views.record_edit, name="record-create"),
    path(
        "app/<slug:module>/<int:pk>/editar/",
        views.record_edit,
        name="record-edit",
    ),
    path(
        "app/<slug:module>/<int:pk>/excluir/",
        views.record_delete,
        name="record-delete",
    ),
    path("emails/enviar/", views.send_notice, name="send-email-notice"),
]
