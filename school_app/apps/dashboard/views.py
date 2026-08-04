import json
import logging
from datetime import timedelta

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db import connection
from django.utils import timezone
from students.models import Student
from teachers.models import Teacher
from classes.models import Classe, AnneeScolaire
from subjects.models import Matiere, MatiereClasse
from bulletin.models import ModeleBulletin
from grades.models import Note
from tenants.models import AnnoncePlateforme, AdminEcole

logger = logging.getLogger('sgn')


@login_required
def communications(request):
    """Communications de la plateforme visibles par l'école connectée."""
    # Les annonces et leur ciblage sont des données de plateforme. Elles
    # doivent donc toujours être lues dans public, même si la requête
    # courante est déjà positionnée sur le schéma d'une école.
    admin_ecole = None
    annonces = []
    public_context = (
        connection.schema_context('public')
        if hasattr(connection, 'schema_context')
        else _null_context()
    )
    with public_context:
        admin_id = request.session.get('admin_ecole_id')
        if admin_id:
            admin_ecole = AdminEcole.objects.select_related('ecole').filter(
                pk=admin_id, is_active=True
            ).first()
        ecole_id = admin_ecole.ecole_id if admin_ecole else None
        now = timezone.now()
        annonces = list(AnnoncePlateforme.objects.filter(
            publiee=True,
        ).filter(
            Q(ecole__isnull=True) | Q(ecole_id=ecole_id)
        ).filter(
            Q(date_expiration__isnull=True) | Q(date_expiration__gte=now)
        ).select_related('ecole'))

    return render(request, 'dashboard/communications.html', {
        'annonces': annonces,
        'admin_ecole': admin_ecole,
    })


class _null_context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


@login_required
def dashboard(request):
    user = request.user
    annee_active = AnneeScolaire.objects.filter(active=True).first()

    if user.is_secretariat():
        # ─── Dashboard Secrétariat ──────────────────────────────────────
        classes_annee = Classe.objects.filter(annee_scolaire=annee_active).select_related('section') if annee_active else Classe.objects.none()
        classes_with_data = list(classes_annee.annotate(nb_eleves=Count('eleves'))[:8])

        # Graphique 1 : élèves par classe (barres)
        chart_classes = {
            'labels': [c.nom for c in classes_with_data],
            'data':   [c.nb_eleves for c in classes_with_data],
        }

        # Graphique 2 : inscriptions sur les 7 derniers jours (ligne)
        today = timezone.now().date()
        labels_7j, data_7j = [], []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            labels_7j.append(day.strftime('%d/%m'))
            data_7j.append(Student.objects.filter(date_inscription=day).count())
        chart_inscriptions = {'labels': labels_7j, 'data': data_7j}

        context = {
            'role': 'secretariat',
            'nb_eleves': Student.objects.count(),
            'nb_enseignants': Teacher.objects.count(),
            'nb_classes': classes_annee.count(),
            'nb_matieres': Matiere.objects.count(),
            'annee_active': annee_active,
            'derniers_eleves': Student.objects.select_related('classe', 'classe__section').order_by('-date_inscription')[:6],
            'dernieres_classes': classes_with_data[:6],
            'chart_classes': chart_classes,
            'chart_inscriptions': chart_inscriptions,
        }
        return render(request, 'dashboard/index_secretariat.html', context)

    if user.is_prefet():
        # ─── Dashboard Préfet ───────────────────────────────────────────
        classes_annee = Classe.objects.filter(annee_scolaire=annee_active).select_related('section') if annee_active else Classe.objects.none()
        bulletins_publies = ModeleBulletin.objects.filter(publie=True).count()
        bulletins_brouillon = ModeleBulletin.objects.filter(publie=False).count()

        # Taux de remplissage des notes (matières affectées avec au moins une note)
        mc_avec_notes = MatiereClasse.objects.filter(notes__isnull=False).distinct().count()
        mc_total = MatiereClasse.objects.count()
        taux_saisie = round(mc_avec_notes / mc_total * 100) if mc_total > 0 else 0

        dernieres_classes_qs = classes_annee.annotate(
            nb_eleves=Count('eleves'),
            nb_matieres=Count('matieres')
        )[:8]

        # Données graphiques
        classes_list = list(dernieres_classes_qs)
        chart_classes = {
            'labels': [c.nom for c in classes_list],
            'data':   [c.nb_eleves for c in classes_list],
        }
        chart_matieres = {
            'labels': [c.nom for c in classes_list],
            'data':   [c.nb_matieres for c in classes_list],
        }
        chart_notes = {
            'labels': ['Notes saisies', 'Restant'],
            'data':   [mc_avec_notes, max(mc_total - mc_avec_notes, 0)],
        }

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
            'dernieres_classes': classes_list,
            'derniers_eleves': Student.objects.select_related('classe', 'classe__section').order_by('-date_inscription')[:6],
            'enseignants_sans_matiere': Teacher.objects.filter(matieres_enseignees__isnull=True)[:5],
            'chart_classes': chart_classes,
            'chart_matieres': chart_matieres,
            'chart_notes': chart_notes,
        }
        return render(request, 'dashboard/index_prefet.html', context)

    if user.is_comptable():
        return redirect('comptable:comptable_dashboard')

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

            # Graphique avancement par affectation (barres horizontales)
            chart_avancement = {
                'labels': [f"{item['affectation'].matiere.nom} — {item['affectation'].classe.nom}" for item in avancement],
                'data':   [item['pct'] for item in avancement],
            }

            # Graphique élèves par classe (doughnut)
            classes_data = list(mes_classes.annotate(nb_el=Count('eleves')))
            chart_classes_enseignant = {
                'labels': [c.nom for c in classes_data],
                'data':   [c.nb_el for c in classes_data],
            }

        except Exception:
            teacher = None
            mes_affectations = MatiereClasse.objects.none()
            mes_classes = Classe.objects.none()
            nb_mes_eleves = 0
            mes_notes_recentes = []
            avancement = []
            chart_avancement = {'labels': [], 'data': []}
            chart_classes_enseignant = {'labels': [], 'data': []}

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
            'chart_avancement': chart_avancement,
            'chart_classes_enseignant': chart_classes_enseignant,
        }
        return render(request, 'dashboard/index_enseignant.html', context)
