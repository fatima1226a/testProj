import json
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers  # pyright: ignore[reportMissingImports]
from rest_framework.settings import api_settings  # pyright: ignore[reportMissingImports]
from server.datasets.models import DatasetRelease
from .models import Run
from .services import create_run
from .payloads import validate_snapshots









class RunSerializer(serializers.ModelSerializer):
    dataset_id = serializers.PrimaryKeyRelatedField(source="dataset", queryset=DatasetRelease.objects.all())
    dataset_notice = serializers.SerializerMethodField()

    def get_dataset_notice(self, instance):
        return "DEMO DATA" if instance.dataset_mode == "demo" else None

    class Meta:
        model = Run
        fields = ("id", "created_at", "site_id", "plan", "result", "dataset_id", "dataset_mode", "dataset_notice", "label")
        read_only_fields = ("id", "created_at", "dataset_mode", "dataset_notice")

    def to_internal_value(self, data):
        allowed = {"label"} if self.instance is not None else {"site_id", "plan", "result", "dataset_id", "label"}
        if not isinstance(data, dict) or data.keys() - allowed:
            # to_internal_value errors must be a dict; a bare string makes DRF fail with 500.
            raise serializers.ValidationError({api_settings.NON_FIELD_ERRORS_KEY:
                                               ["Unknown or read-only fields; only label can be edited"]})
        return super().to_internal_value(data)



    def validate(self, attrs):
        if self.instance is not None:
            return attrs
        for name in ("plan", "result"):
            if not isinstance(attrs[name], dict):
                raise serializers.ValidationError({name: "Expected a JSON object"})
        try:
            validate_snapshots(attrs["plan"], attrs["result"])
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        site_ids = {s["id"] for s in json.loads(bytes(attrs["dataset"].sites_body))["sites"]}
        if attrs["site_id"] not in site_ids or attrs["plan"].get("siteId") != attrs["site_id"]:
            raise serializers.ValidationError("site_id must match the plan and the selected dataset")
        # Results remain client snapshots; no scientific recomputation happens here.
        return attrs

    def create(self, validated_data):
        return create_run(user=self.context["request"].user, **validated_data)
