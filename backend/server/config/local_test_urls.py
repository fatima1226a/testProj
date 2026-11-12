"""Local test routes: real views, with JWT endpoints deliberately omitted."""
from django.urls import include, path
from django.views.generic import RedirectView
from server.accounts.views import RegisterView
from server.docs import docs_asset, openapi_schema, swagger_ui

urlpatterns = [
    path("api/auth/register/", RegisterView.as_view(), name="register"),
    path("api/datasets/", include("server.datasets.urls")),
    path("api/runs/", include("server.runs.urls")),
    path("api/mission/", include("server.mission.urls")),
    path("api/", swagger_ui, name="api-root"),
    path("swagger/", swagger_ui, name="swagger-ui"),
    path("api/docs/", swagger_ui, name="api-docs"),
    path("api/docs/assets/<str:filename>", docs_asset, name="docs-asset"),
    path("api/schema/", openapi_schema, name="openapi-schema"),
    path("", RedirectView.as_view(pattern_name="swagger-ui", permanent=False)),
]
