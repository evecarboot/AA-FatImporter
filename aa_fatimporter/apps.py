"""App Configuration"""

from django.apps import AppConfig

from aa_fatimporter import __version__


class AAFatImporterConfig(AppConfig):
    """App Config"""

    name = "aa_fatimporter"
    label = "aa_fatimporter"
    verbose_name = f"AA FAT Importer v{__version__}"

    def ready(self):
        # Import hooks to register AA menu items and URLs.
        # Wrapped in try/except so the app remains importable in test environments
        # where allianceauth is not installed.
        try:
            import aa_fatimporter.auth_hooks  # noqa: F401
        except ImportError:
            pass

        # Register Celery beat schedule for ESI wallet auto-matching.
        # Runs every 30 minutes to check pending withdrawals against wallet journals.
        try:
            from celery.schedules import crontab
            from django.conf import settings

            beat_schedule = getattr(settings, "CELERYBEAT_SCHEDULE", None)
            if beat_schedule is None:
                beat_schedule = {}
                settings.CELERYBEAT_SCHEDULE = beat_schedule

            beat_schedule.setdefault(
                "aa_fatimporter_match_pending_payouts",
                {
                    "task": "aa_fatimporter.tasks.match_pending_payouts",
                    "schedule": crontab(minute="*/30"),
                },
            )
        except Exception:
            pass
