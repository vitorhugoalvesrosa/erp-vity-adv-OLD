from django.db import models


class ERPUserBootstrap(models.Model):
    name = models.CharField(max_length=50, unique=True)
    completed_at = models.DateTimeField(auto_now_add=True)


class ERPAdminPasswordReset(models.Model):
    token_hash = models.CharField(max_length=64, unique=True)
    completed_at = models.DateTimeField(auto_now_add=True)
