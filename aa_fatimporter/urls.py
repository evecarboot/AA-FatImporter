from django.urls import path

from aa_fatimporter.views import FatImportView, FatLeaderboardView

urlpatterns = [
    path("fat-import/", FatImportView.as_view(), name="aa_fatimport_upload"),
    path("fat-leaderboard/", FatLeaderboardView.as_view(), name="aa_fatimport_dashboard"),
]
