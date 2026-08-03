from django.urls import path
from . import views

urlpatterns = [
    # Planning principal
    path('',                          views.planning_list,      name='planning_list'),
    path('seance/nouvelle/',          views.seance_create,      name='seance_create'),
    path('seance/<int:pk>/modifier/', views.seance_update,      name='seance_update'),
    path('seance/<int:pk>/supprimer/',views.seance_delete,      name='seance_delete'),

    # AJAX — filtrage matières par classe
    path('ajax/matieres/',            views.matieres_par_classe, name='matieres_par_classe'),

    # Mon planning (enseignant)
    path('mon-planning/',             views.mon_planning,       name='mon_planning'),

    # Salles
    path('salles/',                   views.salle_list,         name='salle_list'),
    path('salles/<int:pk>/modifier/', views.salle_update,       name='salle_update'),
    path('salles/<int:pk>/supprimer/',views.salle_delete,       name='salle_delete'),

    # Créneaux horaires
    path('creneaux/',                       views.creneau_list,   name='creneau_list'),
    path('creneaux/<int:pk>/modifier/',     views.creneau_update, name='creneau_update'),
    path('creneaux/<int:pk>/supprimer/',    views.creneau_delete, name='creneau_delete'),
]
