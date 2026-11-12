from django.urls import path
from .views import DatasetDocumentView, DatasetListView

urlpatterns = [path("", DatasetListView.as_view(), name="dataset-list")]
for document in ("sites", "provenance", "validation"):
    urlpatterns.append(path(f"<str:dataset_id>/{document}/", DatasetDocumentView.as_view(),
                            {"document": document}, name=f"dataset-{document}"))
