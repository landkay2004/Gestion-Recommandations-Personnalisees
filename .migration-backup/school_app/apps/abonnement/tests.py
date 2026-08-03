from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import RequestFactory, SimpleTestCase

from . import views


class AbonnementViewsTest(SimpleTestCase):
    def test_messages_middleware_is_before_middlewares_that_use_messages(self):
        message_middleware = 'django.contrib.messages.middleware.MessageMiddleware'
        self.assertIn(message_middleware, settings.MIDDLEWARE)
        self.assertLess(
            settings.MIDDLEWARE.index(message_middleware),
            settings.MIDDLEWARE.index('config.middleware.AbonnementMiddleware'),
        )

    def test_demande_changement_redirects_to_namespaced_subscription_page(self):
        request = RequestFactory().post('/abonnement/changer-plan/', {'plan_id': '1'})
        request.session = {'tenant_schema': 'tenant_test'}
        request.user = SimpleNamespace(is_authenticated=True)

        fake_ecole = SimpleNamespace(
            nom='École de test',
            plan=SimpleNamespace(nom='Actuel'),
            contact_nom='Admin',
            contact_email='admin@example.com',
        )
        fake_plan = SimpleNamespace(
            pk=1,
            nom='Essentiel',
            prix_mensuel=0,
            is_actif=True,
            est_public=True,
        )

        class FakeQuerySet:
            def filter(self, *args, **kwargs):
                return self

            def order_by(self, *args, **kwargs):
                return [fake_plan]

            def get(self, *args, **kwargs):
                return fake_plan

        class FakeEcoleQuerySet:
            def select_related(self, *args, **kwargs):
                return self

            def get(self, *args, **kwargs):
                return fake_ecole

        tenants_module = ModuleType('tenants.models')
        tenants_module.Ecole = SimpleNamespace(objects=FakeEcoleQuerySet())
        tenants_module.PlanAbonnement = SimpleNamespace(objects=FakeQuerySet())

        with patch.dict('sys.modules', {'tenants.models': tenants_module, 'tenants': ModuleType('tenants')}), \
             patch('abonnement.views._envoyer_demande_email'), \
             patch.object(views, 'messages') as messages_mock, \
             patch.object(views, 'redirect', side_effect=lambda name: name) as redirect_mock:
            response = views.demande_changement(request)

        self.assertEqual(response, 'abonnement:mon_abonnement')
        redirect_mock.assert_called_once_with('abonnement:mon_abonnement')
        messages_mock.success.assert_called_once()
