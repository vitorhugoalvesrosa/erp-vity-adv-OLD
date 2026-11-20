from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("administracao/", views.administration, name="admin-settings"),
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
