from django.urls import include, path
from django.conf import settings
from django.contrib import admin
from django.views.generic import RedirectView
from server import docs

urlpatterns = [path("api/", include("server.native_urls"))] if settings.API_BACKEND == "django" else [
    path("api/auth/", include("server.accounts.urls")),
    path("api/datasets/", include("server.datasets.urls")),
    path("api/runs/", include("server.runs.urls")),
]

urlpatterns += [
    path("api/mission/", include("server.mission.urls")),
    path("api/", docs.swagger_ui, name="api-root"),
    path("swagger/", docs.swagger_ui, name="swagger-ui"),
    path("api/docs/", docs.swagger_ui, name="api-docs"),
    path("api/schema/", docs.openapi_schema, name="openapi-schema"),
    path("api/docs/assets/<str:filename>", docs.docs_asset, name="docs-asset"),
    path("", RedirectView.as_view(pattern_name="swagger-ui", permanent=False)),
    path("admin/", admin.site.urls),
]
