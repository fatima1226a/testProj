from hashlib import sha256
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import DatasetRelease

class PublicDatasetView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

class DatasetListView(PublicDatasetView):
    def get(self, request):
        return Response(list(DatasetRelease.objects.order_by("dataset_id").values("dataset_id", "mode", "created_at")))

class DatasetDocumentView(PublicDatasetView):
    def get(self, request, dataset_id, document):
        release = get_object_or_404(DatasetRelease, pk=dataset_id)
        body = bytes(getattr(release, f"{document}_body"))
        return HttpResponse(body, content_type="application/json",
                            headers={"ETag": f'"{sha256(body).hexdigest()}"'})
