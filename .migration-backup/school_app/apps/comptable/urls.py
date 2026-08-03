from django.urls import path
from . import views

app_name = 'comptable'

urlpatterns = [
    # ── Gestion des comptables (admin_ecole) ──────────────────────────────
    path('',                                    views.comptable_list,           name='comptable_list'),
    path('nouveau/',                            views.comptable_create,         name='comptable_create'),
    path('<int:pk>/edit/',                      views.comptable_update,         name='comptable_update'),
    path('<int:pk>/reset-password/',            views.comptable_reset_password, name='comptable_reset_password'),

    # ── Espace caisse (comptable) ─────────────────────────────────────────
    path('caisse/',                             views.comptable_dashboard,      name='comptable_dashboard'),
    path('caisse/recherche/',                   views.recherche_eleve,          name='recherche_eleve'),
    path('caisse/paiement/<int:eleve_pk>/',     views.encaissement,             name='encaissement'),
    path('caisse/historique/',                  views.historique_paiements,     name='historique_paiements'),
    path('caisse/facture/<int:pk>/',            views.facture_detail,           name='facture_detail'),
    path('caisse/facture/<int:pk>/pdf/',        views.facture_pdf,              name='facture_pdf'),
]
