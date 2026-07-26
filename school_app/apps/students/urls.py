from django.urls import path
from . import views

urlpatterns = [
    path('', views.student_list, name='student_list'),
    path('nouveau/', views.student_create, name='student_create'),
    path('<int:pk>/', views.student_detail, name='student_detail'),
    path('<int:pk>/modifier/', views.student_update, name='student_update'),
    path('<int:pk>/supprimer/', views.student_delete, name='student_delete'),
]
