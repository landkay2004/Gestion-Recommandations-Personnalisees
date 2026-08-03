"""URLs publiques (sans authentification) pour EducNet."""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.rejoindre_educnet, name='rejoindre_educnet'),
    path('formulaire/', views.rejoindre_educnet_form, name='rejoindre_educnet_form'),
    path('apropos/', views.about_view, name='about_view'),
    path('contact/', views.contact_view, name='contact_view'),
]
