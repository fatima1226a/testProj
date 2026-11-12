from hashlib import sha256
from django.core.exceptions import ValidationError
from django.db import models

class DatasetRelease(models.Model):
    dataset_id = models.CharField(max_length=200, primary_key=True)
    mode = models.CharField(max_length=5, choices=[("demo", "demo"), ("final", "final")])
    sites_body = models.BinaryField()
    provenance_body = models.BinaryField()
    validation_body = models.BinaryField()
    sites_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if sha256(bytes(self.sites_body)).hexdigest() != self.sites_sha256:
            raise ValidationError("sites.json SHA-256 mismatch")
        existing = type(self).objects.filter(pk=self.pk).first()
        if existing:
            for field in ("mode", "sites_body", "provenance_body", "validation_body", "sites_sha256"):
                if getattr(existing, field) != getattr(self, field):
                    raise ValidationError("Dataset releases are immutable; use a new datasetId")
        super().save(*args, **kwargs)
