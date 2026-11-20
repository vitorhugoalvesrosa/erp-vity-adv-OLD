from django.db import models


class ERPUserBootstrap(models.Model):
    name = models.CharField(max_length=50, unique=True)
    completed_at = models.DateTimeField(auto_now_add=True)
