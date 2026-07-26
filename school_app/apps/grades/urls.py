from django.urls import path
from . import views

urlpatterns = [
    path('', views.saisie_notes, name='saisie_notes'),
    path('consulter/', views.consulter_notes, name='consulter_notes'),
    path('autosave/', views.autosave_note, name='autosave_note'),
    path('export-excel/', views.export_notes_excel, name='export_notes_excel'),
    path('import-excel/', views.import_notes_excel, name='import_notes_excel'),
    path('import-preview/', views.import_notes_preview, name='import_notes_preview'),
    path('historique/', views.historique_notes, name='historique_notes'),
]
