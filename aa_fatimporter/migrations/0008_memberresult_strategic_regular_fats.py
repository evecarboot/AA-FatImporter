from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("aa_fatimporter", "0007_general"),
    ]

    operations = [
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
    ]
