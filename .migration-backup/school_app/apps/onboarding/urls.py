from django.urls import path
from . import views

app_name = 'onboarding'

urlpatterns = [
    path('',          views.etape_courante,      name='etape_courante'),
    path('etape-1/',  views.etape1_password,     name='etape1_password'),
    path('etape-2/',  views.etape2_config,       name='etape2_config'),
    path('etape-3/',  views.etape3_recapitulatif, name='etape3_recapitulatif'),
    path('etape-4/',  views.etape4_conditions,   name='etape4_conditions'),
    path('termine/',  views.termine,             name='termine'),
]
