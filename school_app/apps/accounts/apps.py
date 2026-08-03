from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        """Configure la connexion SQLite avec WAL mode pour de meilleures performances."""
        from django.db.backends.signals import connection_created

        def _set_sqlite_pragmas(sender, connection, **kwargs):
            if connection.vendor == 'sqlite':
                with connection.cursor() as cursor:
                    cursor.execute('PRAGMA journal_mode=WAL;')
                    cursor.execute('PRAGMA synchronous=NORMAL;')
                    cursor.execute('PRAGMA cache_size=-2000;')    # ~2 MB cache (PythonAnywhere)
                    cursor.execute('PRAGMA temp_store=FILE;')     # temp sur disque, pas en RAM
                    cursor.execute('PRAGMA mmap_size=0;')         # désactivé (économise ~256 MB)

        connection_created.connect(_set_sqlite_pragmas)
