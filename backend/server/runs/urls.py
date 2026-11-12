from django.urls import path
from .views import RunViewSet

urlpatterns = [
    path("", RunViewSet.as_view({"get": "list", "post": "create"}), name="run-list"),
    path("<int:pk>/", RunViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}), name="run-detail"),
]
