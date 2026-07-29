from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

handler403 = 'django.views.defaults.permission_denied'
handler404 = 'django.views.defaults.page_not_found'
handler500 = 'django.views.defaults.server_error'

urlpatterns = [
    # Super-Admin
    path('super-admin/', include('super_admin.urls', namespace='super_admin')),

    # Onboarding
    path('onboarding/', include('onboarding.urls', namespace='onboarding')),

    # Apps metier
    path('',              include('dashboard.urls')),
    path('login/',        include('accounts.urls')),
    path('dashboard/',    include('dashboard.urls')),
    path('eleves/',       include('students.urls')),
    path('enseignants/',  include('teachers.urls')),
    path('classes/',      include('classes.urls')),
    path('matieres/',     include('subjects.urls')),
    path('bulletins/',    include('bulletin.urls')),
    path('notes/',        include('grades.urls')),
    path('rapports/',     include('reports.urls')),
    path('parametres/',   include('school_settings.urls')),
    path('portail/',      include('portail.urls')),
    path('cartes/',       include('carte_eleve.urls')),
    path('notifications/', include('notifications.urls')),
    path('planning/',     include('planning.urls')),
    path('abonnement/',   include('abonnement.urls', namespace='abonnement')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
