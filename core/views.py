import smtplib

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import views as auth_views
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMessage
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import EmailNoticeForm


def home(request):
    return render(request, "core/home.html")


class ERPPasswordResetView(auth_views.PasswordResetView):
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")

    def form_valid(self, form):
        if not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL:
            form.add_error(
                None,
                "O envio de e-mails ainda não está configurado neste ambiente.",
            )
            return self.form_invalid(form)

        try:
            return super().form_valid(form)
        except (OSError, smtplib.SMTPException) as exc:
            form.add_error(None, f"Não foi possível enviar o e-mail: {exc}")
            return self.form_invalid(form)


@staff_member_required
def send_notice(request):
    if not (request.user.is_superuser or request.user.has_perm("auth.change_user")):
        raise PermissionDenied

    form = EmailNoticeForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        if not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL:
            form.add_error(
                None,
                "O envio de e-mails ainda não está configurado neste ambiente.",
            )
        else:
            recipients = list(form.cleaned_data["recipients"])
            email = EmailMessage(
                subject=form.cleaned_data["subject"],
                body=form.cleaned_data["message"],
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.DEFAULT_FROM_EMAIL],
                bcc=[user.email for user in recipients],
            )
            try:
                sent = email.send(fail_silently=False)
            except (OSError, smtplib.SMTPException) as exc:
                form.add_error(None, f"Não foi possível enviar o e-mail: {exc}")
            else:
                if sent == 1:
                    messages.success(
                        request,
                        f"Comunicado enviado para {len(recipients)} usuário(s).",
                    )
                    return redirect("send-email-notice")
                form.add_error(None, "O servidor de e-mail não aceitou o envio.")

    return render(request, "admin/email_notice_form.html", {"form": form})
