from django.test import TestCase
from django.urls import reverse
from accounts.models import CustomUser
from students.models import Student


class RapportPaginationTests(TestCase):
    def test_rapport_eleves_paginates_list(self):
        user = CustomUser.objects.create_user(
            username='prefet_test',
            email='prefet@example.com',
            password='secret123',
            role='prefet',
        )
        for i in range(25):
            Student.objects.create(
                nom=f'Student{i}',
                postnom='Test',
                prenom='User',
                sexe='M',
                date_naissance='2005-01-01',
                lieu_naissance='Kinshasa',
                matricule=f'EL{i:03d}',
            )

        self.client.force_login(user)
        response = self.client.get(reverse('rapport_eleves'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('page_obj', response.context)
        self.assertEqual(response.context['page_obj'].paginator.count, 25)
        self.assertEqual(response.context['page_obj'].number, 1)
