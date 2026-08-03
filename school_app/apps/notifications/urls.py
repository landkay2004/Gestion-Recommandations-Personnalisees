from django.urls import path
from . import views

urlpatterns = [
    path('',                      views.notification_list,    name='notification_list'),
    path('count/',                views.notification_count,   name='notification_count'),
    path('recentes/',             views.notification_recentes,name='notification_recentes'),
    path('<int:pk>/lire/',        views.marquer_lue,          name='notif_lire'),
    path('tout-lire/',            views.marquer_toutes_lues,  name='notif_tout_lire'),
]
