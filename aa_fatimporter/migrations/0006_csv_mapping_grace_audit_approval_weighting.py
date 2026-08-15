from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("aa_fatimporter", "0005_fatwindowdays_fatexemption"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add strategic_fats and regular_fats to FatImportMemberResult
        migrations.AddField(
            model_name="fatimportmemberresult",
            name="strategic_fats",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="fatimportmemberresult",
            name="regular_fats",
            field=models.PositiveIntegerField(default=0),
        ),
        # #4 CSV column mapping
        migrations.AddField(
            model_name="fatimportsettings",
            name="csv_column_character",
            field=models.CharField(max_length=128, default="Main Character"),
        ),
        migrations.AddField(
            model_name="fatimportsettings",
            name="csv_column_total_fats",
            field=models.CharField(max_length=128, default="Total FATs"),
        ),
        migrations.AddField(
            model_name="fatimportsettings",
            name="csv_column_strategic_fats",
            field=models.CharField(max_length=128, default="Strategic & Deployment"),
        ),
        # #7 Grace period
        migrations.AddField(
            model_name="fatimportsettings",
            name="grace_period_imports",
            field=models.PositiveIntegerField(default=0),
        ),
        # #10 Strategic FAT weighting
        migrations.AddField(
            model_name="fatimportsettings",
            name="strategic_fat_multiplier",
            field=models.DecimalField(max_digits=5, decimal_places=2, default=1),
        ),
        # #11 Notification on group change
        migrations.AddField(
            model_name="fatimportsettings",
            name="notify_on_group_change",
            field=models.BooleanField(default=False),
        ),
        # #14 Multi-import dedup: csv_hash on FatImportRecord
        migrations.AddField(
            model_name="fatimportrecord",
            name="csv_hash",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="fatimportrecord",
            name="imported_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="fat_imports",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # #9 Payout approval workflow
        migrations.AlterField(
            model_name="fatpayoutrecord",
            name="status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("approved", "Approved"), ("paid", "Paid")],
                default="pending",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="fatpayoutrecord",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="fat_payouts_approved",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="fatpayoutrecord",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        # #7 FatMemberComplianceState model
        migrations.CreateModel(
            name="FatMemberComplianceState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("character_name", models.CharField(max_length=255)),
                ("alliance_consecutive_below", models.PositiveIntegerField(default=0)),
                ("corp_consecutive_below", models.PositiveIntegerField(default=0)),
                ("alliance_first_below_at", models.DateTimeField(blank=True, null=True)),
                ("corp_first_below_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fat_compliance_state",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "FAT compliance state",
                "verbose_name_plural": "FAT compliance states",
                "unique_together": {("user", "character_name")},
            },
        ),
        # #8 FatAuditLog model
        migrations.CreateModel(
            name="FatAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "action",
                    models.CharField(
                        choices=[
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
                        ],
                        max_length=32,
                    ),
                ),
                ("character_name", models.CharField(blank=True, default="", max_length=255)),
                ("details", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="fat_audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "verbose_name": "FAT audit log",
                "verbose_name_plural": "FAT audit logs",
            },
        ),
    ]
