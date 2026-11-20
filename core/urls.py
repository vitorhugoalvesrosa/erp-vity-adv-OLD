from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("emails/enviar/", views.send_notice, name="send-email-notice"),
]
