from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("aa_fatimporter", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FatImportSummarySettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="main", max_length=64)),
                ("webhook_url", models.URLField(blank=True, default="")),
                ("webhook_enabled", models.BooleanField(default=False)),
                ("post_import_summary", models.BooleanField(default=False)),
                ("summary_title", models.CharField(default="FAT Import Summary", max_length=128)),
                ("dashboard_top_count", models.PositiveIntegerField(default=5)),
            ],
            options={
                "verbose_name": "FAT import summary settings",
                "verbose_name_plural": "FAT import summary settings",
            },
        ),
        migrations.CreateModel(
            name="FatImportRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
                ("source_label", models.CharField(default="alliance_csv", max_length=64)),
                ("total_records", models.PositiveIntegerField(default=0)),
                ("total_members", models.PositiveIntegerField(default=0)),
                ("required_fats", models.PositiveIntegerField(default=0)),
                ("remove_above_fats", models.PositiveIntegerField(default=0)),
                (
                    "settings",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="fat_import_records",
                        to="aa_fatimporter.fatimportsettings",
                    ),
                ),
            ],
            options={
                "ordering": ["-imported_at"],
            },
        ),
        migrations.CreateModel(
            name="FatImportMemberResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("character_name", models.CharField(max_length=255)),
                ("total_fats", models.PositiveIntegerField(default=0)),
                ("alliance_action", models.CharField(default="none", max_length=16)),
                ("corp_action", models.CharField(default="none", max_length=16)),
                ("below_alliance_minimum", models.BooleanField(default=False)),
                ("above_remove_threshold", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "record",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="member_results",
                        to="aa_fatimporter.fatimportrecord",
                    ),
                ),
            ],
            options={
                "ordering": ["-total_fats", "character_name"],
            },
        ),
    ]
