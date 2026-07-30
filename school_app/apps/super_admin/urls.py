from django.urls import path
from . import views

app_name = 'super_admin'

urlpatterns = [
    # Auth
    path('login/',    views.login_view,  name='login'),
    path('logout/',   views.logout_view, name='logout'),
    path('2fa/',      views.verify_2fa,  name='verify_2fa'),

    # Dashboard
    path('',          views.dashboard,   name='dashboard'),

    # Écoles
    path('ecoles/',                                  views.ecole_list,              name='ecole_list'),
    path('ecoles/nouvelle/',                         views.ecole_creer,             name='ecole_creer'),
    path('ecoles/<int:pk>/',                         views.ecole_detail,            name='ecole_detail'),
    path('ecoles/<int:pk>/modifier/',                views.ecole_modifier,          name='ecole_modifier'),
    path('ecoles/<int:pk>/suspendre/',               views.ecole_suspendre,         name='ecole_suspendre'),
    path('ecoles/<int:pk>/reactiver/',               views.ecole_reactiver,         name='ecole_reactiver'),
    path('ecoles/<int:pk>/supprimer/',               views.ecole_supprimer,         name='ecole_supprimer'),
    path('ecoles/<int:pk>/restaurer/',               views.ecole_restaurer,         name='ecole_restaurer'),
    path('ecoles/<int:pk>/supprimer-definitif/',     views.ecole_supprimer_definitif, name='ecole_supprimer_definitif'),
    path('ecoles/<int:pk>/regenerer-mdp/',           views.regenerer_mdp_admin,     name='regenerer_mdp_admin'),
    path('ecoles/<int:pk>/abonnement/',              views.abonnement_ecole,        name='abonnement_ecole'),

    # Corbeille
    path('corbeille/',  views.corbeille_list,  name='corbeille_list'),

    # Plans
    path('plans/',                       views.plan_list,          name='plan_list'),
    path('plans/nouveau/',               views.plan_creer,         name='plan_creer'),
    path('plans/<int:pk>/modifier/',     views.plan_modifier,      name='plan_modifier'),
    path('plans/<int:pk>/supprimer/',    views.plan_supprimer,     name='plan_supprimer'),
    path('plans/<int:pk>/toggle/',       views.plan_toggle_actif,  name='plan_toggle_actif'),

    # Quotas
    path('quotas/',   views.quotas_view,  name='quotas'),

    # Maintenance
    path('maintenance/',                  views.maintenance_list,   name='maintenance_list'),
    path('maintenance/nouvelle/',         views.maintenance_creer,  name='maintenance_creer'),
    path('maintenance/<int:pk>/toggle/',  views.maintenance_toggle, name='maintenance_toggle'),

    # Communications
    path('communications/',                    views.communication_list,      name='communication_list'),
    path('communications/nouvelle/',           views.communication_creer,     name='communication_creer'),
    path('communications/<int:pk>/supprimer/', views.communication_supprimer, name='communication_supprimer'),

    # Profil & 2FA
    path('profil/',         views.profil,      name='profil'),
    path('profil/2fa/',     views.setup_2fa,   name='setup_2fa'),
    path('profil/2fa/off/', views.disable_2fa, name='disable_2fa'),

    # Paramètres
    path('parametres/',             views.platform_settings, name='platform_settings'),
    path('parametres/test-email/',  views.test_email,        name='test_email'),
]
