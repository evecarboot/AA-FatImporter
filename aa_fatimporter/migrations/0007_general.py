from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("aa_fatimporter", "0006_csv_mapping_grace_audit_approval_weighting"),
    ]

    operations = [
        migrations.CreateModel(
            name="General",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
            ],
            options={
                "permissions": (("basic_access", "Can access this app"),),
                "managed": False,
                "default_permissions": (),
            },
        ),
    ]
