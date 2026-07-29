from django.urls import path
from . import views

app_name = 'abonnement'

urlpatterns = [
    path('',                views.mon_abonnement,    name='mon_abonnement'),
    path('suspendue/',      views.ecole_suspendue,   name='suspendue'),
    path('changer-plan/',   views.demande_changement, name='demande_changement'),
]
