from django.db import ProgrammingError
from django.test import RequestFactory, SimpleTestCase

from config.middleware import SessionTenantMiddleware
from tenants.models import Ecole


class EcoleAccessTests(SimpleTestCase):
    def test_deleted_school_is_not_accessible(self):
        ecole = Ecole(statut='corbeille', is_deleted=True)
        self.assertFalse(ecole.is_accessible)

    def test_active_school_is_accessible(self):
        ecole = Ecole(statut='active', is_deleted=False)
        self.assertTrue(ecole.is_accessible)


class SessionTenantMiddlewareTests(SimpleTestCase):
    def test_missing_table_error_redirects_to_login(self):
        factory = RequestFactory()

        def raise_missing_table(request):
            raise ProgrammingError("relation 'accounts_customuser' does not exist")

        middleware = SessionTenantMiddleware(raise_missing_table)
        request = factory.get('/eleves/')
        request.session = {}

        response = middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login/')
