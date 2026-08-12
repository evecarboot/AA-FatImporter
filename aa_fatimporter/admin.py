from django.contrib import admin

from aa_fatimporter.models import FatImportSettings


@admin.register(FatImportSettings)
class FatImportSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "same_group_for_both",
        "alliance_group",
        "corp_group",
        "alliance_required_fats_per_90_days",
        "corp_required_fats_per_90_days",
    )
    search_fields = ("name",)
    fieldsets = (
        (
            "Alliance FAT reporting",
            {
                "fields": (
                    "alliance_required_fats_per_90_days",
                    "alliance_remove_above_fats",
                    "alliance_group",
                    "alliance_group_enabled",
                )
            },
        ),
        (
            "Corp FAT compliance",
            {
                "fields": (
                    "corp_required_fats_per_90_days",
                    "corp_remove_group_above_fats",
                    "corp_group",
                    "corp_group_enabled",
                )
            },
        ),
        (
            "Shared options",
            {
                "fields": (
                    "same_group_for_both",
                    "payout_enabled",
                    "payout_method",
                    "reward_for_strategic_fat",
                    "reward_for_regular_fat",
                    "webhook_url",
                )
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("alliance_group", "corp_group")
