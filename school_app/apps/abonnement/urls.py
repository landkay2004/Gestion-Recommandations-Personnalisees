from django.urls import path
from . import views

app_name = 'abonnement'

urlpatterns = [
    # ── Abonnement plateforme ─────────────────────────────────────────────
    path('',                   views.mon_abonnement,     name='mon_abonnement'),
    path('suspendue/',         views.ecole_suspendue,    name='ecole_suspendue'),
    path('changer-plan/',      views.demande_changement, name='demande_changement'),
    path('payer/',             views.soumettre_paiement, name='soumettre_paiement'),

    # ── Types de frais (admin_ecole) ──────────────────────────────────────
    path('frais/',                views.frais_list,   name='frais_list'),
    path('frais/nouveau/',        views.frais_create, name='frais_create'),
    path('frais/<int:pk>/edit/',  views.frais_update, name='frais_update'),
    path('frais/<int:pk>/suppr/', views.frais_delete, name='frais_delete'),
]
