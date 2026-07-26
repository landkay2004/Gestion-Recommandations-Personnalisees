from django.urls import path
from . import views

urlpatterns = [
    path('eleves/', views.rapport_eleves, name='rapport_eleves'),
    path('enseignants/', views.rapport_enseignants, name='rapport_enseignants'),
    path('resultats/', views.rapport_resultats, name='rapport_resultats'),
]
