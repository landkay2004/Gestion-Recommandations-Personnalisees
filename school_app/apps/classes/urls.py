from django.urls import path
from . import views

urlpatterns = [
    # Années scolaires
    path('annees/', views.annee_list, name='annee_list'),
    path('annees/nouvelle/', views.annee_create, name='annee_create'),
    path('annees/<int:pk>/modifier/', views.annee_update, name='annee_update'),
    path('annees/<int:pk>/supprimer/', views.annee_delete, name='annee_delete'),
    path('annees/<int:pk>/activer/', views.annee_activer, name='annee_activer'),
    path('annees/<int:pk>/reconduire/', views.reconduire_annee, name='reconduire_annee'),
    path('annees/<int:pk>/cloture/', views.cloture_annee, name='cloture_annee'),
    path('annees/<int:pk>/promotion/', views.promotion_eleves, name='promotion_eleves'),
    path('journal/', views.journal_operations, name='journal_operations'),

    # Niveaux
    path('niveaux/', views.niveau_list, name='niveau_list'),
    path('niveaux/nouveau/', views.niveau_create, name='niveau_create'),
    path('niveaux/<int:pk>/modifier/', views.niveau_update, name='niveau_update'),
    path('niveaux/<int:pk>/supprimer/', views.niveau_delete, name='niveau_delete'),

    # Sections
    path('sections/', views.section_list, name='section_list'),
    path('sections/nouvelle/', views.section_create, name='section_create'),
    path('sections/<int:pk>/modifier/', views.section_update, name='section_update'),
    path('sections/<int:pk>/supprimer/', views.section_delete, name='section_delete'),

    # Classes
    path('', views.classe_list, name='classe_list'),
    path('nouvelle/', views.classe_create, name='classe_create'),
    path('<int:pk>/modifier/', views.classe_update, name='classe_update'),
    path('<int:pk>/supprimer/', views.classe_delete, name='classe_delete'),

    # Semestres
    path('semestres/', views.semestre_list, name='semestre_list'),
    path('semestres/initialiser/<int:annee_pk>/', views.semestre_initialiser, name='semestre_initialiser'),
    path('semestres/<int:pk>/activer/', views.semestre_activer, name='semestre_activer'),
    path('semestres/<int:pk>/publier/', views.semestre_publier, name='semestre_publier'),
    path('semestres/<int:pk>/archiver/', views.semestre_archiver, name='semestre_archiver'),
    path('semestres/<int:pk>/repechage/', views.semestre_toggle_repechage, name='semestre_toggle_repechage'),
]
