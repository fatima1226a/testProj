from django.apps import AppConfig  # type: ignore[reportMissingModuleSource]

class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "server.accounts"
