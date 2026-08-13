from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect, render
from django.views.generic import FormView, View

from aa_fatimporter.forms import FatUploadForm
from aa_fatimporter.models import (
    FatImportMemberResult,
    FatImportRecord,
    FatImportSettings,
    FatImportSummarySettings,
)
from aa_fatimporter.services import (
    apply_member_fat_rules,
    parse_fat_csv,
    resolve_user_for_character_name,
    send_import_summary_webhook,
    sync_member_group,
)


class FatLeaderboardView(UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def get(self, request):
        settings = FatImportSettings.objects.first()
        summary_settings = FatImportSummarySettings.objects.first()
        latest = FatImportRecord.objects.select_related("settings").first()
        members = []
        if latest:
            members = list(latest.member_results.all())

        context = {
            "settings": settings,
            "summary_settings": summary_settings,
            "latest_import": latest,
            "members": sorted(members, key=lambda item: (-item.total_fats, item.character_name)),
            "title": getattr(summary_settings or settings, "summary_title", "FAT Leaderboard"),
        }
        return render(request, "aa_fatimporter/leaderboard.html", context)


class FatImportView(UserPassesTestMixin, FormView):
    template_name = "aa_fatimporter/upload.html"
    form_class = FatUploadForm
    success_url = "/"

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def form_valid(self, form):
        uploaded_file = form.cleaned_data["csv_file"]
        data = uploaded_file.read().decode("utf-8", errors="replace")
        records = parse_fat_csv(data)

        if not records:
            messages.error(self.request, "No valid FAT rows were found in the uploaded CSV.")
            return redirect(self.success_url)

        settings = FatImportSettings.objects.first()
        if settings is None:
            settings = FatImportSettings.objects.create(name="main")

        result = apply_member_fat_rules(records, settings)
        member_details = result.get("members", {})

        import_record = FatImportRecord.objects.create(
            settings=settings,
            total_records=len(records),
            total_members=len(member_details),
            required_fats=getattr(settings, "alliance_required_fats_per_90_days", 0),
            remove_above_fats=getattr(settings, "alliance_remove_above_fats", 0),
        )

        for name, details in member_details.items():
            user = resolve_user_for_character_name(name)
            below_minimum = details.get("total_fats", 0) < getattr(settings, "alliance_required_fats_per_90_days", 0)
            above_remove = details.get("total_fats", 0) > getattr(settings, "alliance_remove_above_fats", 0)
            FatImportMemberResult.objects.create(
                record=import_record,
                character_name=name,
                total_fats=details.get("total_fats", 0),
                alliance_action=details.get("alliance_action", "none"),
                corp_action=details.get("corp_action", "none"),
                below_alliance_minimum=below_minimum,
                above_remove_threshold=above_remove,
            )

            if not user:
                continue

            total_fats = details.get("total_fats", 0)

            alliance_group = getattr(settings, "alliance_group", None)
            corp_group = getattr(settings, "corp_group", None)

            if getattr(settings, "same_group_for_both", False):
                alliance_group = alliance_group or corp_group
                corp_group = alliance_group

            if getattr(settings, "alliance_group_enabled", False) and alliance_group is not None:
                alliance_threshold = getattr(settings, "alliance_required_fats_per_90_days", 0)
                alliance_remove_above = getattr(settings, "alliance_remove_above_fats", None)
                sync_member_group(
                    user,
                    total_fats,
                    alliance_threshold,
                    group_id=alliance_group.pk,
                    remove_above_fats=alliance_remove_above,
                )

            if getattr(settings, "corp_group_enabled", False) and corp_group is not None:
                corp_threshold = getattr(settings, "corp_required_fats_per_90_days", 0)
                corp_remove_above = getattr(settings, "corp_remove_group_above_fats", None)
                sync_member_group(
                    user,
                    total_fats,
                    corp_threshold,
                    group_id=corp_group.pk,
                    remove_above_fats=corp_remove_above,
                )

        summary_settings = FatImportSummarySettings.objects.first()
        if summary_settings is None and settings is not None:
            summary_settings = settings

        if getattr(summary_settings, "post_import_summary", False) and getattr(summary_settings, "webhook_url", ""):
            send_import_summary_webhook(records, summary_settings)

        messages.success(
            self.request,
            f"Imported {len(records)} FAT entries and evaluated {len(member_details)} member totals.",
        )
        return super().form_valid(form)
