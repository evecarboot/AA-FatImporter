from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("aa_fatimporter", "0002_fatimportsummarysettings_fatimportrecord_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FatPayoutRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("character_name", models.CharField(max_length=255)),
                ("strategic_fats", models.PositiveIntegerField(default=0)),
                ("regular_fats", models.PositiveIntegerField(default=0)),
                ("total_fats", models.PositiveIntegerField(default=0)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                (
                    "payout_method",
                    models.CharField(
                        choices=[("withdrawal", "Member withdrawal"), ("invoice_deduction", "Deduct from corp tax bill"), ("manual", "No automatic payout")],
                        default="manual",
                        max_length=32,
                    ),
                ),
                ("status", models.CharField(choices=[("pending", "Pending"), ("paid", "Paid")], default="pending", max_length=16)),
                ("payout_ref", models.CharField(blank=True, db_index=True, default="", max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                (
                    "record",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payouts",
                        to="aa_fatimporter.fatimportrecord",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="fat_payouts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "verbose_name": "FAT payout",
                "verbose_name_plural": "FAT payouts",
                "unique_together": {("record", "character_name")},
            },
        ),
    ]
