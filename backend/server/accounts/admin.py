from django.contrib import admin  # type: ignore[reportMissingModuleSource]
from django.contrib.auth.admin import UserAdmin  # type: ignore[reportMissingModuleSource]

from .models import User


admin.site.register(User, UserAdmin)
