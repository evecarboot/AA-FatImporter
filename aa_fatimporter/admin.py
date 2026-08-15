import csv

from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone

from aa_fatimporter.models import (
    FatAuditLog,
    FatExemption,
    FatImportMemberResult,
    FatImportRecord,
    FatImportSettings,
    FatImportSummarySettings,
    FatMemberComplianceState,
    FatPayoutRecord,
)
from aa_fatimporter.services import log_audit_event


@admin.register(FatImportSummarySettings)
class FatImportSummarySettingsAdmin(admin.ModelAdmin):
    list_display = ("name", "webhook_enabled", "post_import_summary", "summary_title")
    search_fields = ("name", "summary_title")
    fieldsets = (
        (
            "Discord import summary webhook",
            {
                "fields": (
                    "webhook_enabled",
                    "webhook_url",
                    "post_import_summary",
                    "summary_title",
                    "dashboard_top_count",
                )
            },
        ),
    )


@admin.register(FatImportSettings)
class FatImportSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "fat_window_days",
        "same_group_for_both",
        "alliance_group",
        "corp_group",
        "alliance_required_fats_per_90_days",
        "corp_required_fats_per_90_days",
    )
    search_fields = ("name",)
    fieldsets = (
        (
            "Compliance window",
            {
                "fields": ("fat_window_days", "grace_period_imports", "strategic_fat_multiplier"),
            },
        ),
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
            "CSV column mapping",
            {
                "fields": (
                    "csv_column_character",
                    "csv_column_total_fats",
                    "csv_column_strategic_fats",
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
                    "notify_on_group_change",
                )
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("alliance_group", "corp_group")


class FatImportMemberResultInline(admin.TabularInline):
    model = FatImportMemberResult
    extra = 0
    can_delete = False
    max_num = 0
    fields = ("character_name", "total_fats", "strategic_fats", "regular_fats", "alliance_action", "corp_action", "below_alliance_minimum", "above_remove_threshold")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(FatImportRecord)
class FatImportRecordAdmin(admin.ModelAdmin):
    list_display = ("imported_at", "source_label", "total_records", "total_members", "required_fats", "remove_above_fats", "imported_by")
    list_filter = ("source_label",)
    search_fields = ("settings__name", "csv_hash")
    ordering = ("-imported_at",)
    inlines = [FatImportMemberResultInline]
    actions = ("export_member_results",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("settings", "imported_by")

    @admin.action(description="Export member results as CSV")
    def export_member_results(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="fat_import_results.csv"'
        writer = csv.writer(response)
        writer.writerow(["Import Date", "Character", "Total FATs", "Alliance Action", "Corp Action", "Below Min", "Above Remove"])
        for record in queryset:
            for result in record.member_results.all():
                writer.writerow([
                    record.imported_at.strftime("%Y-%m-%d %H:%M"),
                    result.character_name,
                    result.total_fats,
                    result.alliance_action,
                    result.corp_action,
                    result.below_alliance_minimum,
                    result.above_remove_threshold,
                ])
        return response


@admin.register(FatPayoutRecord)
class FatPayoutRecordAdmin(admin.ModelAdmin):
    list_display = ("character_name", "amount", "payout_method", "status", "payout_ref", "created_at", "approved_by", "paid_at")
    list_filter = ("status", "payout_method")
    search_fields = ("character_name", "payout_ref", "user__username")
    ordering = ("-created_at",)
    actions = ("approve_payouts", "mark_paid", "check_esi_matches", "export_payouts")
    readonly_fields = ("record", "user", "character_name", "strategic_fats", "regular_fats", "total_fats", "amount", "payout_method", "payout_ref", "created_at", "approved_by", "approved_at")

    fieldsets = (
        (None, {"fields": ("record", "user", "character_name", "status", "approved_by", "approved_at", "paid_at")}),
        ("FAT breakdown", {"fields": ("strategic_fats", "regular_fats", "total_fats")}),
        ("Payout", {"fields": ("amount", "payout_method", "payout_ref", "created_at")}),
    )

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "record", "approved_by")

    @admin.action(description="Approve selected payouts")
    def approve_payouts(self, request, queryset):
        updated = queryset.filter(status="pending").update(
            status="approved", approved_by=request.user, approved_at=timezone.now()
        )
        for payout in queryset.filter(status="approved"):
            log_audit_event("payout_approved", user=request.user, character_name=payout.character_name,
                            details=f"Approved payout {payout.payout_ref}")
        self.message_user(request, f"Approved {updated} payout(s).")

    @admin.action(description="Mark selected payouts as paid (requires approval first)")
    def mark_paid(self, request, queryset):
        updated = queryset.filter(status="approved").update(status="paid", paid_at=timezone.now())
        if updated == 0:
            pending_count = queryset.filter(status="pending").count()
            if pending_count:
                self.message_user(request, f"Cannot mark {pending_count} payout(s) as paid — approve them first.")
            else:
                self.message_user(request, "No approved payouts to mark as paid.")
        else:
            for payout in queryset.filter(status="paid"):
                log_audit_event("payout_paid", user=request.user, character_name=payout.character_name,
                                details=f"Marked paid: {payout.payout_ref}")
            self.message_user(request, f"Marked {updated} payout(s) as paid.")

    @admin.action(description="Check ESI wallet for matching ISK transfers")
    def check_esi_matches(self, request, queryset):
        from aa_fatimporter.tasks import match_pending_payouts

        pending = queryset.filter(status__in=["pending", "approved"], payout_ref__gt="")
        if not pending.exists():
            self.message_user(request, "No pending/approved payouts with a payout_ref to check.")
            return

        refs = list(pending.values_list("payout_ref", flat=True))
        match_pending_payouts.apply_async(args=[refs])
        self.message_user(request, f"Queued ESI wallet match check for {len(refs)} payout(s).")

    @admin.action(description="Export selected payouts as CSV")
    def export_payouts(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="fat_payouts.csv"'
        writer = csv.writer(response)
        writer.writerow(["Character", "Amount", "Method", "Status", "Payout Ref", "Created", "Approved By", "Paid At"])
        for p in queryset:
            writer.writerow([
                p.character_name, p.amount, p.payout_method, p.status,
                p.payout_ref, p.created_at.strftime("%Y-%m-%d %H:%M"),
                p.approved_by.username if p.approved_by else "",
                p.paid_at.strftime("%Y-%m-%d %H:%M") if p.paid_at else "",
            ])
        return response


@admin.register(FatExemption)
class FatExemptionAdmin(admin.ModelAdmin):
    list_display = ("character_name", "user", "scope", "reason", "start_date", "end_date", "created_at")
    list_filter = ("scope",)
    search_fields = ("character_name", "user__username", "reason")
    ordering = ("-created_at",)
    fieldsets = (
        (None, {"fields": ("user", "character_name", "scope", "reason")}),
        ("Date range (optional)", {"fields": ("start_date", "end_date")}),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(FatMemberComplianceState)
class FatMemberComplianceStateAdmin(admin.ModelAdmin):
    list_display = ("character_name", "user", "alliance_consecutive_below", "corp_consecutive_below", "alliance_first_below_at", "updated_at")
    list_filter = ("alliance_consecutive_below", "corp_consecutive_below")
    search_fields = ("character_name", "user__username")
    ordering = ("-updated_at",)
    readonly_fields = ("user", "character_name", "alliance_consecutive_below", "corp_consecutive_below", "alliance_first_below_at", "corp_first_below_at", "updated_at")

    def has_add_permission(self, request):
        return False


@admin.register(FatAuditLog)
class FatAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "character_name", "user", "details")
    list_filter = ("action",)
    search_fields = ("character_name", "user__username", "details")
    ordering = ("-created_at",)
    readonly_fields = ("user", "action", "character_name", "details", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
