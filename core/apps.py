from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"
    default_auto_field = "django.db.models.BigAutoField"
    
    def ready(self):
        """Import signals when the app is ready."""
        import core.signals  # noqa: F401
