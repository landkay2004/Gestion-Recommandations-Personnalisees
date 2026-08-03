from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from school_settings.views import manifest_view, manifest_portail_view, favicon_view
from django.views.defaults import page_not_found, server_error

handler403 = 'django.views.defaults.permission_denied'
handler404 = 'django.views.defaults.page_not_found'
handler500 = 'django.views.defaults.server_error'

urlpatterns = [
    # PWA — sw.js doit être servi à la racine pour contrôler tout le site
    path('sw.js', TemplateView.as_view(
        template_name='sw.js',
        content_type='application/javascript',
    ), name='sw'),
    # Manifests PWA — servis avec contexte SchoolInfo
    path('manifest.json', manifest_view, name='manifest'),
    path('portail/manifest.json', manifest_portail_view, name='manifest_portail'),
    path('favicon.ico', favicon_view, name='favicon'),
    path('favicon.png', favicon_view, name='favicon_png'),

    path('', include('dashboard.urls')),
    path('login/', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('eleves/', include('students.urls')),
    path('enseignants/', include('teachers.urls')),
    path('classes/', include('classes.urls')),
    path('matieres/', include('subjects.urls')),
    path('bulletins/', include('bulletin.urls')),
    path('notes/', include('grades.urls')),
    path('rapports/', include('reports.urls')),
    path('parametres/', include('school_settings.urls')),
    path('portail/', include('portail.urls')),
    path('cartes/', include('carte_eleve.urls')),
    path('notifications/', include('notifications.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
