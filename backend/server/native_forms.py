"""Django form validation for the native JSON API."""
import json
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .datasets.models import DatasetRelease
from .runs.payloads import validate_snapshots

class RegisterForm(forms.ModelForm):
    password = forms.CharField(strip=False)

    class Meta:
        model = get_user_model()
        fields = ("username", "email", "password")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists")
        return email

    def clean(self):
        values = super().clean()
        if "password" in values:
            validate_password(values["password"], get_user_model()(
                username=values.get("username", ""), email=values.get("email", "")))
        return values

    def save(self):
        return get_user_model().objects.create_user(**self.cleaned_data)

class ObjectField(forms.Field):
    """Already parsed JSON object; unlike JSONField it neither decodes strings nor treats {} as missing (as in DRF)."""

    def to_python(self, value):
        if not isinstance(value, dict):
            raise forms.ValidationError("Expected a JSON object")
        return value

    def validate(self, value):
        pass

class RunCreateForm(forms.Form):
    dataset_id = forms.ModelChoiceField(queryset=DatasetRelease.objects.all())
    site_id = forms.CharField(max_length=200)
    plan = ObjectField()
    result = ObjectField()
    label = forms.CharField(max_length=200, required=False)

    def clean(self):
        values = super().clean()
        if all(key in values for key in ("plan", "result")):
            validate_snapshots(values["plan"], values["result"])
        if all(key in values for key in ("dataset_id", "site_id", "plan")):
            sites = json.loads(bytes(values["dataset_id"].sites_body))["sites"]
            if values["site_id"] not in {s["id"] for s in sites} or values["plan"].get("siteId") != values["site_id"]:
                raise forms.ValidationError("site_id must match the plan and selected dataset")
        return values
