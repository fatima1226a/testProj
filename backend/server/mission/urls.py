from django.urls import path

from .views import mission

app_name = "mission"

urlpatterns = [
    path("", mission, name="mission"),
]
