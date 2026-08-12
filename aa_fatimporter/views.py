from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect
from django.views.generic import FormView

from aa_fatimporter.forms import FatUploadForm
from aa_fatimporter.models import FatImportSettings
from aa_fatimporter.services import (
    apply_member_fat_rules,
    parse_fat_csv,
    resolve_user_for_character_name,
    sync_member_group,
)


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

        for name, details in member_details.items():
            user = resolve_user_for_character_name(name)
            if not user:
                continue

            total_fats = details.get("total_fats", 0)

            alliance_group = getattr(settings, "alliance_group", None)
            corp_group = getattr(settings, "corp_group", None)

            if getattr(settings, "same_group_for_both", False):
                alliance_group = alliance_group or corp_group
                corp_group = alliance_group

            if alliance_group is not None:
                alliance_threshold = getattr(settings, "alliance_required_fats_per_90_days", 0)
                alliance_remove_above = getattr(settings, "alliance_remove_above_fats", None)
                sync_member_group(
                    user,
                    total_fats,
                    alliance_threshold,
                    group_id=alliance_group.pk,
                    remove_above_fats=alliance_remove_above,
                )

            if corp_group is not None:
                corp_threshold = getattr(settings, "corp_required_fats_per_90_days", 0)
                corp_remove_above = getattr(settings, "corp_remove_group_above_fats", None)
                sync_member_group(
                    user,
                    total_fats,
                    corp_threshold,
                    group_id=corp_group.pk,
                    remove_above_fats=corp_remove_above,
                )

        messages.success(
            self.request,
            f"Imported {len(records)} FAT entries and evaluated {len(member_details)} member totals.",
        )
        return super().form_valid(form)
