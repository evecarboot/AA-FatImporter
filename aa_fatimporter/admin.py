from django.contrib import admin

from aa_fatimporter.models import FatImportSettings


@admin.register(FatImportSettings)
class FatImportSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "required_fats_per_90_days",
        "payout_enabled",
        "payout_method",
        "below_threshold_role_id",
    )
    search_fields = ("name",)
