from django.urls import path
from . import views

urlpatterns = [
    path('',                        views.carte_list,   name='carte_list'),
    path('config/',                 views.carte_config, name='carte_config'),
    path('<int:pk>/',               views.carte_preview, name='carte_preview'),
    path('classe/<int:classe_id>/', views.cartes_classe, name='cartes_classe'),
]
