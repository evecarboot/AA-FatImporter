from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("aa_fatimporter", "0004_alter_name_unique"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="fatimportsettings",
            name="fat_window_days",
            field=models.PositiveIntegerField(default=90),
        ),
        migrations.CreateModel(
            name="FatExemption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("character_name", models.CharField(blank=True, default="", max_length=255)),
                ("scope", models.CharField(choices=[("alliance", "Alliance only"), ("corp", "Corp only"), ("both", "Both alliance and corp")], default="both", max_length=16)),
                ("reason", models.CharField(blank=True, default="", max_length=255)),
                ("start_date", models.DateTimeField(blank=True, null=True)),
                ("end_date", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fat_exemptions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="fat_exemptions_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "verbose_name": "FAT exemption",
                "verbose_name_plural": "FAT exemptions",
            },
        ),
    ]
