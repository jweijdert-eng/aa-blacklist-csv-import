from django.urls import path

from . import views

app_name = "blacklist_csv_import"

urlpatterns = [
    path("", views.upload_csv, name="upload"),
    path("names/", views.add_names, name="add_names"),
]
