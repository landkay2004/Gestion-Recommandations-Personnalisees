from django.urls import path
from . import views

urlpatterns = [
    path('', views.teacher_list, name='teacher_list'),
    path('nouveau/', views.teacher_create, name='teacher_create'),
    path('<int:pk>/', views.teacher_detail, name='teacher_detail'),
    path('<int:pk>/modifier/', views.teacher_update, name='teacher_update'),
    path('<int:pk>/supprimer/', views.teacher_delete, name='teacher_delete'),
]
