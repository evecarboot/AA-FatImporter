from django.apps import AppConfig


class AAFatImporterConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aa_fatimporter"
    label = "aa_fatimporter"
    verbose_name = "AA FAT Importer"

    def ready(self):
        import aa_fatimporter.hooks  # noqa: F401
