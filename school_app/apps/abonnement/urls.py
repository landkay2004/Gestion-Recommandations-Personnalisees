from django.urls import path
from . import views

app_name = 'abonnement'

urlpatterns = [
    # ── Abonnement école ──────────────────────────────────────────────────
    path('',                      views.mon_abonnement,      name='mon_abonnement'),
    path('suspendue/',            views.ecole_suspendue,     name='ecole_suspendue'),
    path('changer-plan/',         views.demande_changement,  name='demande_changement'),

    # ── Types de frais (admin_ecole) ──────────────────────────────────────
    path('frais/',                views.frais_list,          name='frais_list'),
    path('frais/nouveau/',        views.frais_create,        name='frais_create'),
    path('frais/<int:pk>/edit/',  views.frais_update,        name='frais_update'),
    path('frais/<int:pk>/suppr/', views.frais_delete,        name='frais_delete'),

    # ── Gestion des comptables (admin_ecole) ──────────────────────────────
    path('comptables/',                         views.comptable_list,           name='comptable_list'),
    path('comptables/nouveau/',                 views.comptable_create,         name='comptable_create'),
    path('comptables/<int:pk>/edit/',           views.comptable_update,         name='comptable_update'),
    path('comptables/<int:pk>/reset-password/', views.comptable_reset_password, name='comptable_reset_password'),

    # ── Espace comptable ──────────────────────────────────────────────────
    path('caisse/',                              views.comptable_dashboard,    name='comptable_dashboard'),
    path('caisse/recherche/',                    views.recherche_eleve,        name='recherche_eleve'),
    path('caisse/paiement/<int:eleve_pk>/',      views.encaissement,           name='encaissement'),
    path('caisse/historique/',                   views.historique_paiements,   name='historique_paiements'),
    path('caisse/facture/<int:pk>/',             views.facture_detail,         name='facture_detail'),
    path('caisse/facture/<int:pk>/pdf/',         views.facture_pdf,            name='facture_pdf'),
]
