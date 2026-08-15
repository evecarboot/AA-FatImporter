from django.conf import settings as django_settings
from django.contrib.auth.models import Group
from django.db import models


class General(models.Model):
    """Meta model for app permissions."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (("basic_access", "Can access this app"),)


class FatImportSettings(models.Model):
    """Admin-configurable settings for the FAT importer.

    The alliance CSV is imported as a reporting dataset. Corp and alliance compliance are tracked
    separately and can use the same AA group if the admin chooses.
    """

    name = models.CharField(max_length=64, default="main", unique=True)

    # Configurable FAT compliance window (days). Defaults to 90 but can be set
    # to 30, 60, or any other value by the admin.
    fat_window_days = models.PositiveIntegerField(default=90)

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
    last_imported_at = models.DateTimeField(blank=True, null=True)

    # CSV column mapping (#4) — configurable column names for different FAT export formats.
    csv_column_character = models.CharField(max_length=128, default="Main Character")
    csv_column_total_fats = models.CharField(max_length=128, default="Total FATs")
    csv_column_strategic_fats = models.CharField(max_length=128, default="Strategic & Deployment")

    # Grace period (#7) — number of consecutive imports a member can be below minimum
    # before group removal is applied. 0 = no grace period (immediate removal).
    grace_period_imports = models.PositiveIntegerField(default=0)

    # Strategic FAT weighting (#10) — multiplier applied to strategic FATs for compliance.
    # e.g. 2.0 means 1 strategic FAT counts as 2 regular FATs. 1.0 = no weighting.
    strategic_fat_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1)

    # Notification on group change (#11) — when enabled, notify members when they are
    # added to or removed from a compliance group.
    notify_on_group_change = models.BooleanField(default=False)

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

    name = models.CharField(max_length=64, default="main", unique=True)
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
    csv_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)
    imported_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fat_imports",
    )

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
    strategic_fats = models.PositiveIntegerField(default=0)
    regular_fats = models.PositiveIntegerField(default=0)
    alliance_action = models.CharField(max_length=16, default="none")
    corp_action = models.CharField(max_length=16, default="none")
    below_alliance_minimum = models.BooleanField(default=False)
    above_remove_threshold = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-total_fats", "character_name"]

    def __str__(self):
        return f"{self.character_name}: {self.total_fats} FATs"


class FatPayoutRecord(models.Model):
    """Ledger of member FAT payouts created on import.

    Records the calculated ISK payout for each member per import. A unique ``payout_ref``
    is generated for every payout so a director can include it in the in-game ISK transfer
    reason field; a Celery task then scans wallet journal entries for matching refs and
    auto-marks payouts as ``paid``. ``invoice_deduction`` payouts are created as ``paid``
    immediately when the corresponding invoice is successfully created.
    """

    PAYOUT_METHODS = [
        ("withdrawal", "Member withdrawal"),
        ("invoice_deduction", "Deduct from corp tax bill"),
        ("manual", "No automatic payout"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("paid", "Paid"),
    ]

    record = models.ForeignKey(
        FatImportRecord,
        on_delete=models.CASCADE,
        related_name="payouts",
    )
    user = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fat_payouts",
    )
    character_name = models.CharField(max_length=255)
    strategic_fats = models.PositiveIntegerField(default=0)
    regular_fats = models.PositiveIntegerField(default=0)
    total_fats = models.PositiveIntegerField(default=0)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    payout_method = models.CharField(max_length=32, choices=PAYOUT_METHODS, default="manual")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    payout_ref = models.CharField(max_length=128, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fat_payouts_approved",
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "FAT payout"
        verbose_name_plural = "FAT payouts"
        unique_together = [("record", "character_name")]

    def __str__(self):
        return f"{self.character_name}: {self.amount} ISK ({self.payout_method}, {self.status})"


class FatExemption(models.Model):
    """Exempt a member from FAT compliance checks for a period of time.

    Used for new recruits, LOA/away members, alts, or leadership who should not
    be subject to group removal for missing FAT requirements. Exemptions can target
    alliance compliance, corp compliance, or both, and have optional start/end dates.
    """

    SCOPE_CHOICES = [
        ("alliance", "Alliance only"),
        ("corp", "Corp only"),
        ("both", "Both alliance and corp"),
    ]

    user = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fat_exemptions",
    )
    character_name = models.CharField(max_length=255, blank=True, default="")
    scope = models.CharField(max_length=16, choices=SCOPE_CHOICES, default="both")
    reason = models.CharField(max_length=255, blank=True, default="")
    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fat_exemptions_created",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "FAT exemption"
        verbose_name_plural = "FAT exemptions"

    def __str__(self):
        return f"{self.character_name or self.user}: {self.scope} exemption"

    @property
    def is_active(self):
        """Return True if this exemption is currently within its date range."""
        try:
            from django.utils import timezone
            now = timezone.now()
            if self.start_date and now < self.start_date:
                return False
            if self.end_date and now > self.end_date:
                return False
            return True
        except Exception:
            return True


class FatMemberComplianceState(models.Model):
    """Track a member's compliance state across imports for grace period calculation.

    Records the number of consecutive imports a member has been below the alliance
    or corp minimum. Used by the grace period logic to delay group removal until
    the member has been below minimum for a configurable number of imports.
    """

    user = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fat_compliance_state",
    )
    character_name = models.CharField(max_length=255)
    alliance_consecutive_below = models.PositiveIntegerField(default=0)
    corp_consecutive_below = models.PositiveIntegerField(default=0)
    alliance_first_below_at = models.DateTimeField(blank=True, null=True)
    corp_first_below_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "FAT compliance state"
        verbose_name_plural = "FAT compliance states"
        unique_together = [("user", "character_name")]

    def __str__(self):
        return f"{self.character_name}: alliance_below={self.alliance_consecutive_below}, corp_below={self.corp_consecutive_below}"


class FatAuditLog(models.Model):
    """Audit trail of FAT import and compliance actions."""

    ACTION_CHOICES = [
        ("import", "CSV import"),
        ("group_add", "Group add"),
        ("group_remove", "Group remove"),
        ("group_skip_exempt", "Group skip (exempt)"),
        ("group_skip_grace", "Group skip (grace period)"),
        ("payout_created", "Payout created"),
        ("payout_approved", "Payout approved"),
        ("payout_paid", "Payout paid"),
        ("webhook_sent", "Webhook sent"),
        ("webhook_failed", "Webhook failed"),
        ("duplicate_warning", "Duplicate import warning"),
    ]

    user = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fat_audit_logs",
    )
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    character_name = models.CharField(max_length=255, blank=True, default="")
    details = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "FAT audit log"
        verbose_name_plural = "FAT audit logs"

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} - {self.action} - {self.character_name}"
