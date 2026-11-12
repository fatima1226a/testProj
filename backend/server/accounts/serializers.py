from django.contrib.auth import get_user_model  # type: ignore[reportMissingModuleSource]
from django.contrib.auth.password_validation import validate_password  # type: ignore[reportMissingModuleSource]
from django.core.exceptions import ValidationError as DjangoValidationError  # type: ignore[reportMissingModuleSource]
from django.db import IntegrityError, transaction  # type: ignore[reportMissingModuleSource]
from rest_framework import serializers  # type: ignore[reportMissingImports]

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = get_user_model()
        fields = ("id", "username", "email", "password")
        read_only_fields = ("id",)
        extra_kwargs = {"email": {"required": True, "allow_blank": False}}

    def validate_email(self, value):
        value = value.strip().lower()
        if get_user_model().objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists")
        return value

    def validate(self, attrs):
        try:
            validate_password(attrs["password"], get_user_model()(
                username=attrs.get("username", ""), email=attrs.get("email", "")))
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from error
        return attrs

    def create(self, validated_data):
        # A concurrent registration can pass validate_email before either insert commits.
        try:
            with transaction.atomic():
                return get_user_model().objects.create_user(**validated_data)
        except IntegrityError as error:
            raise serializers.ValidationError("Username or email already exists") from error
