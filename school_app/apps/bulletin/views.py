from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Q, Value, DecimalField
from django.db.models.functions import Coalesce
from .models import ModeleBulletin, ModeleBulletinMatiere
from accounts.views import prefet_required
from grades.models import Note
from students.models import Student
from subjects.models import Matiere, MatiereClasse
from classes.models import Classe, AnneeScolaire
from decimal import Decimal


@login_required
def bulletin_list(request):
    bulletins = ModeleBulletin.objects.select_related(
        'classe', 'classe__section', 'annee_scolaire'
    ).order_by('annee_scolaire', 'classe__nom')
    return render(request, 'bulletin/bulletin_list.html', {'bulletins': bulletins})


@login_required
@prefet_required
def bulletin_create(request):
    annee   = AnneeScolaire.objects.filter(active=True).first()
    classes = Classe.objects.filter(annee_scolaire=annee).select_related('section') if annee else []

    classe_id      = request.GET.get('classe') or request.POST.get('classe')
    selected_classe = None
    matieres_20 = matieres_30 = matieres_60 = []

    if classe_id:
        selected_classe = get_object_or_404(Classe, pk=classe_id)
        mc_qs       = MatiereClasse.objects.filter(classe=selected_classe).select_related('matiere')
        matieres_20 = [mc.matiere for mc in mc_qs if mc.matiere.maxima == 20]
        matieres_30 = [mc.matiere for mc in mc_qs if mc.matiere.maxima == 30]
        matieres_60 = [mc.matiere for mc in mc_qs if mc.matiere.maxima == 60]

    if request.method == 'POST' and selected_classe:
        annee_id  = request.POST.get('annee_scolaire')
        annee_obj = get_object_or_404(AnneeScolaire, pk=annee_id) if annee_id else annee

        modele, created = ModeleBulletin.objects.get_or_create(
            classe=selected_classe, annee_scolaire=annee_obj
        )
        modele.matieres.all().delete()

        all_matieres = matieres_20 + matieres_30 + matieres_60
        ordre = 0
        for m in all_matieres:
            if request.POST.get(f'mat_{m.pk}'):
                ModeleBulletinMatiere.objects.create(modele=modele, matiere=m, ordre=ordre)
                ordre += 1

        messages.success(request, f"Modèle de bulletin {'créé' if created else 'mis à jour'} pour {selected_classe}.")
        return redirect('bulletin_list')

    if request.method == 'POST' and not selected_classe:
        messages.error(request, "Veuillez sélectionner une classe.")

    return render(request, 'bulletin/bulletin_form.html', {
        'classes': classes, 'annees': AnneeScolaire.objects.all(), 'annee': annee,
        'titre': 'Créer un modèle de bulletin',
        'selected_classe': selected_classe,
        'matieres_20': matieres_20, 'matieres_30': matieres_30, 'matieres_60': matieres_60,
        'selected_ids': set(), 'classe_id': classe_id or '',
    })


@login_required
@prefet_required
def bulletin_update(request, pk):
    modele  = get_object_or_404(ModeleBulletin, pk=pk)
    annee   = AnneeScolaire.objects.filter(active=True).first()
    classes = Classe.objects.filter(annee_scolaire=annee).select_related('section') if annee else []

    mc_qs       = MatiereClasse.objects.filter(classe=modele.classe).select_related('matiere')
    matieres_20 = [mc.matiere for mc in mc_qs if mc.matiere.maxima == 20]
    matieres_30 = [mc.matiere for mc in mc_qs if mc.matiere.maxima == 30]
    matieres_60 = [mc.matiere for mc in mc_qs if mc.matiere.maxima == 60]
    all_matieres = matieres_20 + matieres_30 + matieres_60

    if request.method == 'POST':
        modele.matieres.all().delete()
        ordre = 0
        for m in all_matieres:
            if request.POST.get(f'mat_{m.pk}'):
                ModeleBulletinMatiere.objects.create(modele=modele, matiere=m, ordre=ordre)
                ordre += 1
        messages.success(request, "Modèle mis à jour.")
        return redirect('bulletin_list')

    selected_ids = set(modele.matieres.values_list('matiere_id', flat=True))
    return render(request, 'bulletin/bulletin_form.html', {
        'classes': classes, 'annees': AnneeScolaire.objects.all(), 'annee': annee,
        'titre': f'Modifier le bulletin — {modele.classe}',
        'obj': modele, 'selected_classe': modele.classe,
        'matieres_20': matieres_20, 'matieres_30': matieres_30, 'matieres_60': matieres_60,
        'selected_ids': selected_ids, 'classe_id': str(modele.classe.pk),
    })


@login_required
@prefet_required
def bulletin_delete(request, pk):
    modele = get_object_or_404(ModeleBulletin, pk=pk)
    if request.method == 'POST':
        modele.delete()
        messages.success(request, "Modèle supprimé.")
        return redirect('bulletin_list')
    return render(request, 'bulletin/bulletin_confirm_delete.html', {'obj': modele})


@login_required
@prefet_required
def bulletin_publish(request, pk):
    modele = get_object_or_404(ModeleBulletin, pk=pk)
    if request.method == 'POST':
        modele.publie = True
        modele.date_publication = timezone.now()
        modele.save()
        messages.success(request, f"Résultats publiés pour {modele.classe}.")
    return redirect('bulletin_list')


@login_required
def bulletin_classe(request, pk):
    modele = get_object_or_404(ModeleBulletin, pk=pk)
    if request.user.is_enseignant():
        messages.error(request, "Accès réservé au Préfet.")
        return redirect('dashboard')
    eleves = Student.objects.filter(classe=modele.classe).order_by('nom', 'postnom')
    return render(request, 'bulletin/bulletin_classe.html', {'modele': modele, 'eleves': eleves})


@login_required
def bulletin_eleve(request, pk, eleve_pk):
    modele = get_object_or_404(ModeleBulletin, pk=pk)
    if request.user.is_enseignant():
        messages.error(request, "Accès réservé au Préfet.")
        return redirect('dashboard')
    eleve = get_object_or_404(Student, pk=eleve_pk)

    # ── Optimisation : 1 seule requête pour toutes les MatiereClasse de la classe ──
    mc_map = {
        mc.matiere_id: mc
        for mc in MatiereClasse.objects.filter(classe=modele.classe).select_related('matiere')
    }

    # ── Optimisation : 1 seule requête pour toutes les notes de l'élève dans cette classe ──
    notes_lookup = {
        (n.matiere_classe_id, n.periode): n.valeur
        for n in Note.objects.filter(eleve=eleve, matiere_classe__classe=modele.classe)
    }

    PERIODES = ('1P', '2P', 'EXAM1', '3P', '4P', 'EXAM2', 'REPECHAGE')
    matieres_data = []
    total_obtenu  = Decimal('0')
    total_max_tg  = Decimal('0')

    for bm in modele.matieres.select_related('matiere').order_by('matiere__maxima', 'ordre'):
        mat = bm.matiere
        mc  = mc_map.get(mat.pk)

        notes_dict = {}
        if mc:
            for p in PERIODES:
                notes_dict[p] = notes_lookup.get((mc.pk, p))
        else:
            notes_dict = {p: None for p in PERIODES}

        mx   = mat.maxima
        n1p  = notes_dict.get('1P')    or Decimal('0')
        n2p  = notes_dict.get('2P')    or Decimal('0')
        ne1  = notes_dict.get('EXAM1') or Decimal('0')
        n3p  = notes_dict.get('3P')    or Decimal('0')
        n4p  = notes_dict.get('4P')    or Decimal('0')
        ne2  = notes_dict.get('EXAM2') or Decimal('0')

        has_s1 = any(notes_dict.get(p) is not None for p in ('1P', '2P', 'EXAM1'))
        has_s2 = any(notes_dict.get(p) is not None for p in ('3P', '4P', 'EXAM2'))

        tot_s1 = (n1p + n2p + ne1) if has_s1 else None
        tot_s2 = (n3p + n4p + ne2) if has_s2 else None
        tg     = (tot_s1 or Decimal('0')) + (tot_s2 or Decimal('0'))
        max_tg = Decimal(mx) * 8

        total_obtenu += tg
        total_max_tg += max_tg

        matieres_data.append({
            'matiere':   mat,
            'n1p':       notes_dict.get('1P'),
            'n2p':       notes_dict.get('2P'),
            'nexam1':    notes_dict.get('EXAM1'),
            'tot_s1':    tot_s1,
            'n3p':       notes_dict.get('3P'),
            'n4p':       notes_dict.get('4P'),
            'nexam2':    notes_dict.get('EXAM2'),
            'tot_s2':    tot_s2,
            'tg':        tg,
            'repechage': notes_dict.get('REPECHAGE'),
        })

    pourcentage = round(float(total_obtenu) / float(total_max_tg) * 100, 2) if total_max_tg else 0
    classement  = _get_classement(modele, eleve, total_obtenu)
    nb_eleves   = eleve.classe.eleves.count() if eleve.classe else 0

    return render(request, 'bulletin/bulletin_eleve.html', {
        'modele':        modele,
        'eleve':         eleve,
        'matieres_data': matieres_data,
        'total_obtenu':  round(float(total_obtenu), 1),
        'total_max':     round(float(total_max_tg), 1),
        'pourcentage':   pourcentage,
        'classement':    classement,
        'nb_eleves':     nb_eleves,
    })


def _get_classement(modele, eleve, my_score):
    """
    Classement de l'élève dans sa classe.
    Optimisé : 1 seule requête SQL avec agrégation au lieu d'une boucle N+1.
    """
    scores_qs = (
        Student.objects.filter(classe=modele.classe)
        .annotate(
            total=Coalesce(
                Sum(
                    'notes__valeur',
                    filter=Q(notes__matiere_classe__classe=modele.classe)
                           & ~Q(notes__periode='REPECHAGE')
                ),
                Value(Decimal('0')),
                output_field=DecimalField(max_digits=8, decimal_places=2),
            )
        )
        .values_list('total', flat=True)
    )
    scores = sorted(scores_qs, reverse=True)
    try:
        return scores.index(my_score) + 1
    except ValueError:
        return '-'
