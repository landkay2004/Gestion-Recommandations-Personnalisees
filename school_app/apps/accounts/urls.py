from django.urls import path
from . import views

urlpatterns = [
    path('',                                          views.login_view,           name='login'),
    path('logout/',                                   views.logout_view,          name='logout'),
    path('changer-mot-de-passe/',                     views.force_change_password, name='force_change_password'),
    path('profil/',                                   views.profile_view,         name='profile_view'),
    path('utilisateurs/',                             views.user_list,            name='user_list'),
    path('utilisateurs/nouveau/',                     views.user_create,          name='user_create'),
    path('utilisateurs/<int:pk>/modifier/',           views.user_update,          name='user_update'),
    path('utilisateurs/<int:pk>/supprimer/',          views.user_delete,          name='user_delete'),
    path('utilisateurs/<int:pk>/reinitialiser/',      views.reset_user_password,  name='reset_user_password'),
]
