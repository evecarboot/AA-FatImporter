from django.db import models


class FatImportSettings(models.Model):
    """Admin-configurable settings for the FAT importer."""

    name = models.CharField(max_length=64, default="main")
    required_fats_per_90_days = models.PositiveIntegerField(default=10)
    below_threshold_group_name = models.CharField(max_length=255, blank=True, default="")
    below_threshold_role_id = models.BigIntegerField(default=0, blank=True, null=True)
    remove_group_above_fats = models.PositiveIntegerField(default=15)
    payout_enabled = models.BooleanField(default=False)
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

    class Meta:
        verbose_name = "FAT import settings"
        verbose_name_plural = "FAT import settings"

    def __str__(self):
        return self.name
