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
    below_threshold_role_id = models.BigIntegerField(default=0, blank=True, null=True)
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
