from django.urls import path
from . import views

urlpatterns = [
    # ── Élèves ────────────────────────────────────────────────────────────────
    path('', views.student_list, name='student_list'),
    path('nouveau/', views.student_create, name='student_create'),
    path('<int:pk>/', views.student_detail, name='student_detail'),
    path('<int:pk>/modifier/', views.student_update, name='student_update'),
    path('<int:pk>/supprimer/', views.student_delete, name='student_delete'),

    # ── Matricule auto ────────────────────────────────────────────────────────
    path('next-matricule/', views.next_matricule_json, name='next_matricule_json'),

    # ── Tuteurs ───────────────────────────────────────────────────────────────
    path('tuteurs/', views.tuteur_list, name='tuteur_list'),
    path('tuteurs/nouveau/', views.tuteur_create, name='tuteur_create'),
    path('tuteurs/recherche/', views.tuteur_search_json, name='tuteur_search_json'),
    path('tuteurs/<int:pk>/', views.tuteur_detail, name='tuteur_detail'),
    path('tuteurs/<int:pk>/modifier/', views.tuteur_update, name='tuteur_update'),
    path('tuteurs/<int:pk>/supprimer/', views.tuteur_delete, name='tuteur_delete'),
]
