from django.test import TestCase
from django.urls import reverse

from super_admin.models import PlatformSettings


class PublicInscriptionPageTests(TestCase):
    def setUp(self):
        PlatformSettings.objects.get_or_create(pk=1, defaults={'site_name': 'EducNet'})

    def test_public_inscription_form_page_is_available(self):
        response = self.client.get(reverse('rejoindre_educnet_form'))
        self.assertEqual(response.status_code, 200)

    def test_public_landing_page_links_to_dedicated_form_page(self):
        response = self.client.get(reverse('rejoindre_educnet'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('rejoindre_educnet_form'))

    def test_public_landing_page_links_to_dedicated_form_page(self):
        response = self.client.get(reverse('rejoindre_educnet'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/rejoindre/formulaire/')
