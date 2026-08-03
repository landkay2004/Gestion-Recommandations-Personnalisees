from django.urls import path
from . import views
from .pdf_views import bulletin_eleve_pdf

urlpatterns = [
    path('', views.bulletin_list, name='bulletin_list'),
    path('nouveau/', views.bulletin_create, name='bulletin_create'),
    path('<int:pk>/modifier/', views.bulletin_update, name='bulletin_update'),
    path('<int:pk>/supprimer/', views.bulletin_delete, name='bulletin_delete'),
    path('<int:pk>/publier/', views.bulletin_publish, name='bulletin_publish'),
    path('<int:pk>/classe/', views.bulletin_classe, name='bulletin_classe'),
    path('<int:pk>/eleve/<int:eleve_pk>/', views.bulletin_eleve, name='bulletin_eleve'),
    path('<int:pk>/eleve/<int:eleve_pk>/pdf/', bulletin_eleve_pdf, name='bulletin_eleve_pdf'),
]
