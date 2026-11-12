from rest_framework.viewsets import ModelViewSet
from .models import Run
from .serializers import RunSerializer

class RunViewSet(ModelViewSet):
    serializer_class = RunSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        # No staff/superuser exception: every caller sees only their own runs.
        return Run.objects.filter(user=self.request.user).select_related("dataset")
