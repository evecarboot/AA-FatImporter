from django.contrib.auth.models import Group
from django.db import models


class FatImportSettings(models.Model):
    """Admin-configurable settings for the FAT importer.

    The alliance CSV is imported as a reporting dataset. Corp and alliance compliance are tracked
    separately and can use the same AA group if the admin chooses.
    """

    name = models.CharField(max_length=64, default="main")

    # Alliance FAT import/reporting settings
    alliance_required_fats_per_90_days = models.PositiveIntegerField(default=10)
    alliance_remove_above_fats = models.PositiveIntegerField(default=15)
    alliance_group = models.ForeignKey(
        Group,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alliance_fat_group",
    )
    alliance_group_enabled = models.BooleanField(default=False)

    # Corp FAT compliance settings
    corp_required_fats_per_90_days = models.PositiveIntegerField(default=10)
    corp_remove_group_above_fats = models.PositiveIntegerField(default=15)
    corp_group = models.ForeignKey(
        Group,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="corp_fat_group",
    )
    corp_group_enabled = models.BooleanField(default=False)

    # Shared payout settings
    payout_enabled = models.BooleanField(default=False)
    same_group_for_both = models.BooleanField(default=False)
    reward_for_strategic_fat = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    reward_for_regular_fat = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    payout_method = models.CharField(
        max_length=32,
        choices=[
            ("withdrawal", "Member withdrawal"),
            ("invoice_deduction", "Deduct from corp tax bill"),
            ("manual", "No automatic payout"),
        ],
        default="withdrawal",
    )
    webhook_url = models.URLField(blank=True, default="")
    webhook_enabled = models.BooleanField(default=False)
    post_import_summary = models.BooleanField(default=False)
    summary_title = models.CharField(max_length=128, default="FAT Import Summary")
    dashboard_top_count = models.PositiveIntegerField(default=5)
    last_imported_at = models.DateTimeField(blank=True, null=True)

    @property
    def alliance_compliance_group_name(self):
        return self.alliance_group.name if self.alliance_group else ""

    @alliance_compliance_group_name.setter
    def alliance_compliance_group_name(self, value):
        if value:
            self.alliance_group = Group.objects.filter(name=value).first()
        else:
            self.alliance_group = None

    @property
    def corp_compliance_group_name(self):
        return self.corp_group.name if self.corp_group else ""

    @corp_compliance_group_name.setter
    def corp_compliance_group_name(self, value):
        if value:
            self.corp_group = Group.objects.filter(name=value).first()
        else:
            self.corp_group = None

    class Meta:
        verbose_name = "FAT import settings"
        verbose_name_plural = "FAT import settings"

    def __str__(self):
        return self.name


class FatImportSummarySettings(models.Model):
    """Dedicated admin settings for the post-import Discord summary webhook."""

    name = models.CharField(max_length=64, default="main")
    webhook_url = models.URLField(blank=True, default="")
    webhook_enabled = models.BooleanField(default=False)
    post_import_summary = models.BooleanField(default=False)
    summary_title = models.CharField(max_length=128, default="FAT Import Summary")
    dashboard_top_count = models.PositiveIntegerField(default=5)

    class Meta:
        verbose_name = "FAT import summary settings"
        verbose_name_plural = "FAT import summary settings"

    def __str__(self):
        return self.name


class FatImportRecord(models.Model):
    """Store a single CSV import and its summary totals."""

    settings = models.ForeignKey(
        FatImportSettings,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fat_import_records",
    )
    imported_at = models.DateTimeField(auto_now_add=True)
    source_label = models.CharField(max_length=64, default="alliance_csv")
    total_records = models.PositiveIntegerField(default=0)
    total_members = models.PositiveIntegerField(default=0)
    required_fats = models.PositiveIntegerField(default=0)
    remove_above_fats = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-imported_at"]

    def __str__(self):
        return f"FAT import {self.imported_at:%Y-%m-%d %H:%M}"


class FatImportMemberResult(models.Model):
    """Store per-member FAT totals and status for each import."""

    record = models.ForeignKey(
        FatImportRecord,
        on_delete=models.CASCADE,
        related_name="member_results",
    )
    character_name = models.CharField(max_length=255)
    total_fats = models.PositiveIntegerField(default=0)
    alliance_action = models.CharField(max_length=16, default="none")
    corp_action = models.CharField(max_length=16, default="none")
    below_alliance_minimum = models.BooleanField(default=False)
    above_remove_threshold = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-total_fats", "character_name"]

    def __str__(self):
        return f"{self.character_name}: {self.total_fats} FATs"
