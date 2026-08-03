from django.apps import AppConfig


class TenantsConfig(AppConfig):
    name = 'tenants'
    verbose_name = 'Gestion des Écoles (Multi-tenant)'

    def ready(self):
        import tenants.signals  # noqa: F401 — enregistrement des signaux
