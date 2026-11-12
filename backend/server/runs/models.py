from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

class Run(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    site_id = models.CharField(max_length=200)
    plan = models.JSONField()
    result = models.JSONField()
    dataset = models.ForeignKey("datasets.DatasetRelease", on_delete=models.PROTECT)
    dataset_mode = models.CharField(max_length=5, choices=[("demo", "demo"), ("final", "final")])
    label = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["user", "-created_at"], name="runs_user_recent")]

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            for field in ("user_id", "created_at", "site_id", "plan", "result", "dataset_id", "dataset_mode"):
                if getattr(self, field) != getattr(original, field):
                    raise ValidationError("Only label may be changed on a saved run")
        else:
            self.dataset_mode = self.dataset.mode
        super().save(*args, **kwargs)
