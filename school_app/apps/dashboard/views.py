import logging

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from students.models import Student
from teachers.models import Teacher
from classes.models import Classe, AnneeScolaire
from subjects.models import Matiere, MatiereClasse
from bulletin.models import ModeleBulletin
from grades.models import Note

logger = logging.getLogger('sgn')


@login_required
def dashboard(request):
    user = request.user
    annee_active = AnneeScolaire.objects.filter(active=True).first()

    if user.is_prefet():
        # ─── Dashboard Préfet ───────────────────────────────────────────
        classes_annee = Classe.objects.filter(annee_scolaire=annee_active).select_related('section') if annee_active else Classe.objects.none()
        bulletins_publies = ModeleBulletin.objects.filter(publie=True).count()
        bulletins_brouillon = ModeleBulletin.objects.filter(publie=False).count()

        # Taux de remplissage des notes (matières affectées avec au moins une note)
        mc_avec_notes = MatiereClasse.objects.filter(notes__isnull=False).distinct().count()
        mc_total = MatiereClasse.objects.count()
        taux_saisie = round(mc_avec_notes / mc_total * 100) if mc_total > 0 else 0

        context = {
            'role': 'prefet',
            'nb_eleves': Student.objects.count(),
            'nb_enseignants': Teacher.objects.count(),
            'nb_classes': classes_annee.count(),
            'nb_matieres': Matiere.objects.count(),
            'nb_bulletins_publies': bulletins_publies,
            'nb_bulletins_brouillon': bulletins_brouillon,
            'taux_saisie': taux_saisie,
            'mc_avec_notes': mc_avec_notes,
            'mc_total': mc_total,
            'annee_active': annee_active,
            'dernieres_classes': classes_annee.annotate(
                nb_eleves=__import__('django.db.models', fromlist=['Count']).Count('eleves')
            )[:6],
            'derniers_eleves': Student.objects.select_related('classe', 'classe__section').order_by('-date_inscription')[:6],
            'enseignants_sans_matiere': Teacher.objects.filter(matieres_enseignees__isnull=True)[:5],
        }
        return render(request, 'dashboard/index_prefet.html', context)

    else:
        # ─── Dashboard Enseignant ───────────────────────────────────────
        try:
            teacher = user.teacher_profile
            mes_affectations = MatiereClasse.objects.filter(
                enseignant=teacher
            ).select_related('matiere', 'classe', 'classe__section', 'classe__annee_scolaire')

            # Mes classes distinctes
            mes_classes_ids = mes_affectations.values_list('classe_id', flat=True).distinct()
            mes_classes = Classe.objects.filter(pk__in=mes_classes_ids).select_related('section')

            # Nombre d'élèves dans mes classes
            nb_mes_eleves = Student.objects.filter(classe__in=mes_classes).count()

            # Notes récentes que j'ai saisies
            mes_notes_recentes = Note.objects.filter(
                matiere_classe__enseignant=teacher
            ).select_related('eleve', 'matiere_classe__matiere', 'matiere_classe__classe').order_by('-id')[:10]

            # Avancement par matière/classe — annotations SQL (zéro N+1)
            avancement_qs = MatiereClasse.objects.filter(
                enseignant=teacher
            ).select_related(
                'matiere', 'classe', 'classe__section', 'classe__annee_scolaire'
            ).annotate(
                notes_count=Count('notes', distinct=True),
                nb_eleves_count=Count('classe__eleves', distinct=True),
            )[:8]

            avancement = []
            periodes_totales = 7  # 1P, 2P, EXAM1, 3P, 4P, EXAM2, REPECHAGE
            for aff in avancement_qs:
                attendues = aff.nb_eleves_count * periodes_totales
                pct = round(aff.notes_count / attendues * 100) if attendues > 0 else 0
                avancement.append({
                    'affectation': aff,
                    'notes_saisies': aff.notes_count,
                    'attendues': attendues,
                    'pct': pct,
                    'nb_eleves': aff.nb_eleves_count,
                })

        except Exception:
            teacher = None
            mes_affectations = MatiereClasse.objects.none()
            mes_classes = Classe.objects.none()
            nb_mes_eleves = 0
            mes_notes_recentes = []
            avancement = []

        context = {
            'role': 'enseignant',
            'teacher': teacher,
            'mes_affectations': mes_affectations,
            'mes_classes': mes_classes,
            'nb_mes_classes': mes_classes.count(),
            'nb_mes_matieres': mes_affectations.count(),
            'nb_mes_eleves': nb_mes_eleves,
            'avancement': avancement,
            'mes_notes_recentes': mes_notes_recentes,
            'annee_active': annee_active,
        }
        return render(request, 'dashboard/index_enseignant.html', context)
