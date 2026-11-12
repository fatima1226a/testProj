from django.urls import path
from . import native_api as api

urlpatterns = [
    path("auth/csrf/", api.csrf, name="csrf"),
    path("auth/register/", api.register, name="register"),
    path("auth/login/", api.session_login, name="session-login"),
    path("auth/logout/", api.session_logout, name="session-logout"),
    path("auth/token/", api.jwt_unavailable, name="token-unavailable"),
    path("auth/token/refresh/", api.jwt_unavailable, name="refresh-unavailable"),
    path("datasets/", api.datasets, name="dataset-list"),
    path("runs/", api.runs, name="run-list"),
    path("runs/<int:pk>/", api.run_detail, name="run-detail"),
]
for document in ("sites", "provenance", "validation"):
    urlpatterns.append(path(f"datasets/<str:dataset_id>/{document}/", api.dataset_document,
                            {"document": document}, name=f"dataset-{document}"))
