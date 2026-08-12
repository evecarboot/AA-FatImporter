from django.urls import path

from aa_fatimporter.views import FatImportView

urlpatterns = [
    path("fat-import/", FatImportView.as_view(), name="aa_fatimport_upload"),
]
