"""URLs publiques (sans authentification) pour EducNet."""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.rejoindre_educnet, name='rejoindre_educnet'),
]
