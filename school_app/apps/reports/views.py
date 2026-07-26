from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from students.models import Student
from teachers.models import Teacher
from bulletin.models import ModeleBulletin
from grades.models import Note
from classes.models import Classe, AnneeScolaire
from accounts.views import prefet_required
from decimal import Decimal


@login_required
@prefet_required
def rapport_eleves(request):
    annee     = AnneeScolaire.objects.filter(active=True).first()
    classe_id = request.GET.get('classe', '')
    students  = Student.objects.select_related('classe', 'classe__section').order_by('classe__nom', 'nom', 'postnom')
    if classe_id:
        students = students.filter(classe_id=classe_id)
    classes   = Classe.objects.filter(annee_scolaire=annee).select_related('section') if annee else []
    return render(request, 'reports/rapport_eleves.html', {
        'students': students, 'classes': classes,
        'classe_id': classe_id, 'annee': annee,
    })


@login_required
@prefet_required
def rapport_enseignants(request):
    teachers = Teacher.objects.select_related('user').prefetch_related(
        'matieres_enseignees',
        'matieres_enseignees__matiere',
        'matieres_enseignees__classe',
        'matieres_enseignees__classe__section',
    ).order_by('user__last_name', 'user__first_name')
    return render(request, 'reports/rapport_enseignants.html', {'teachers': teachers})


@login_required
@prefet_required
def rapport_resultats(request):
    bulletins  = ModeleBulletin.objects.select_related('classe', 'classe__section', 'annee_scolaire').order_by('annee_scolaire', 'classe__nom')
    modele_id  = request.GET.get('modele', '')
    resultats  = []
    modele     = None
    stats      = {}

    if modele_id:
        modele   = get_object_or_404(ModeleBulletin, pk=modele_id)
        max_total = sum(
            bm.matiere.maxima * 8
            for bm in modele.matieres.select_related('matiere')
        )
        eleves = Student.objects.filter(classe=modele.classe).order_by('nom', 'postnom')

        for eleve in eleves:
            total = Note.objects.filter(
                eleve=eleve,
                matiere_classe__classe=modele.classe
            ).exclude(periode='REPECHAGE').aggregate(total=Sum('valeur'))['total'] or Decimal('0')
            total = round(float(total), 1)

            pct     = round(float(total) / float(max_total) * 100, 2) if max_total else 0
            mention = _mention(pct)
            resultats.append({
                'eleve':      eleve,
                'total':      total,
                'max':        max_total,
                'pourcentage': pct,
                'mention':    mention,
                'admis':      pct >= 50,
            })

        resultats.sort(key=lambda x: x['total'], reverse=True)
        for i, r in enumerate(resultats):
            r['rang'] = i + 1

        # Statistiques de classe
        nb = len(resultats)
        nb_admis  = sum(1 for r in resultats if r['admis'])
        nb_echec  = nb - nb_admis
        pct_reuss = round(nb_admis / nb * 100, 1) if nb else 0
        moy_classe = round(float(sum(r['total'] for r in resultats)) / nb / float(max_total) * 100, 2) if nb else 0

        mentions_count = {}
        for r in resultats:
            mentions_count[r['mention']] = mentions_count.get(r['mention'], 0) + 1

        stats = {
            'nb': nb, 'nb_admis': nb_admis, 'nb_echec': nb_echec,
            'pct_reuss': pct_reuss, 'moy_classe': moy_classe,
            'mentions': mentions_count,
        }

    return render(request, 'reports/rapport_resultats.html', {
        'bulletins':  bulletins,
        'modele_id':  modele_id,
        'modele':     modele,
        'resultats':  resultats,
        'stats':      stats,
    })


def _mention(pct):
    if pct >= 80:   return 'Grande distinction'
    if pct >= 70:   return 'Distinction'
    if pct >= 60:   return 'Satisfaction'
    if pct >= 50:   return 'Réussite'
    return 'Échec'
