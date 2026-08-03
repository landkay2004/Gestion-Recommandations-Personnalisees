from django.urls import path
from . import views

urlpatterns = [
    path('', views.settings_view, name='settings_view'),
    path('matricule/', views.matricule_config_view, name='matricule_config'),
    path('matricule/apercu/', views.matricule_apercu_ajax, name='matricule_apercu'),
]
