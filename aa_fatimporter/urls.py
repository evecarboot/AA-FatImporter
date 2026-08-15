from django.urls import path

from aa_fatimporter.views import (
    FatImportView,
    FatLeaderboardAPI,
    FatLeaderboardView,
    FatPayoutsAPI,
    FatTrendsView,
    FatWhatIfView,
)

app_name = "aa_fatimporter"

urlpatterns = [
    path("fat-import/", FatImportView.as_view(), name="aa_fatimport_upload"),
    path("fat-leaderboard/", FatLeaderboardView.as_view(), name="aa_fatimport_dashboard"),
    path("fat-trends/", FatTrendsView.as_view(), name="aa_fatimport_trends"),
    path("fat-whatif/", FatWhatIfView.as_view(), name="aa_fatimport_whatif"),
    path("api/leaderboard/", FatLeaderboardAPI.as_view(), name="api_leaderboard"),
    path("api/payouts/", FatPayoutsAPI.as_view(), name="api_payouts"),
]
