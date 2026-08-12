from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FatImportSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='main', max_length=64)),
                ('alliance_required_fats_per_90_days', models.PositiveIntegerField(default=10)),
                ('alliance_remove_above_fats', models.PositiveIntegerField(default=15)),
                ('alliance_group_enabled', models.BooleanField(default=False)),
                ('corp_required_fats_per_90_days', models.PositiveIntegerField(default=10)),
                ('corp_remove_group_above_fats', models.PositiveIntegerField(default=15)),
                ('corp_group_enabled', models.BooleanField(default=False)),
                ('payout_enabled', models.BooleanField(default=False)),
                ('same_group_for_both', models.BooleanField(default=False)),
                ('below_threshold_role_id', models.BigIntegerField(blank=True, default=0, null=True)),
                ('reward_for_strategic_fat', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('reward_for_regular_fat', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('payout_method', models.CharField(choices=[('withdrawal', 'Member withdrawal'), ('invoice_deduction', 'Deduct from corp tax bill'), ('manual', 'No automatic payout')], default='withdrawal', max_length=32)),
                ('webhook_url', models.URLField(blank=True, default='')),
                ('last_imported_at', models.DateTimeField(blank=True, null=True)),
                ('alliance_group', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='alliance_fat_group', to='auth.group')),
                ('corp_group', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='corp_fat_group', to='auth.group')),
            ],
            options={
                'verbose_name': 'FAT import settings',
                'verbose_name_plural': 'FAT import settings',
            },
        ),
    ]
