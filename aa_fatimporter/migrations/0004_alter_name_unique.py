from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("aa_fatimporter", "0003_fatpayoutrecord"),
    ]

    operations = [
        migrations.AlterField(
            model_name="fatimportsettings",
            name="name",
            field=models.CharField(max_length=64, default="main", unique=True),
        ),
        migrations.AlterField(
            model_name="fatimportsummarysettings",
            name="name",
            field=models.CharField(max_length=64, default="main", unique=True),
        ),
    ]
