from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from .models import Matiere, MatiereClasse, Maxima
from .forms import MatiereForm, MatiereClasseForm, MaximaForm
from accounts.views import prefet_required
from classes.models import Classe, AnneeScolaire

# Palette de couleurs pour les groupes maxima (cyclique)
_MAXIMA_COLORS = [
    {'badge': 'bg-warning text-dark', 'border': '#D97706', 'bg': 'rgba(217,119,6,0.1)',   'text': '#D97706'},
    {'badge': 'bg-info text-dark',    'border': '#0891B2', 'bg': 'rgba(8,145,178,0.1)',   'text': '#0891B2'},
    {'badge': 'bg-danger',            'border': '#DC2626', 'bg': 'rgba(220,38,38,0.1)',   'text': '#DC2626'},
    {'badge': 'bg-success',           'border': '#059669', 'bg': 'rgba(5,150,105,0.1)',   'text': '#059669'},
    {'badge': 'bg-primary',           'border': '#2563EB', 'bg': 'rgba(37,99,235,0.1)',   'text': '#2563EB'},
    {'badge': 'bg-secondary',         'border': '#6B7280', 'bg': 'rgba(107,114,128,0.1)', 'text': '#6B7280'},
]


def _build_maxima_groups(matieres_qs):
    """Retourne une liste de dicts {valeur, matieres, color} triée par valeur."""
    maxima_objs = list(Maxima.objects.all())
    groups = []
    for i, mx in enumerate(maxima_objs):
        groups.append({
            'valeur': mx.valeur,
            'matieres': matieres_qs.filter(maxima=mx.valeur),
            'color': _MAXIMA_COLORS[i % len(_MAXIMA_COLORS)],
        })
    return groups


def _build_maxima_colors_map():
    """Retourne un dict {valeur: badge_class} pour les badges inline."""
    maxima_objs = list(Maxima.objects.all())
    return {mx.valeur: _MAXIMA_COLORS[i % len(_MAXIMA_COLORS)]['badge']
            for i, mx in enumerate(maxima_objs)}


# ─── Gestion des Maxima ────────────────────────────────────────────────────────

@login_required
@prefet_required
def maxima_list(request):
    maxima = Maxima.objects.all()
    form = MaximaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        valeur = form.cleaned_data['valeur']
        obj, created = Maxima.objects.get_or_create(valeur=valeur)
        if created:
            messages.success(request, f"Maxima {valeur} ajouté.")
        else:
            messages.warning(request, f"MAXIMA {valeur} existe déjà.")
        return redirect('maxima_list')
    return render(request, 'subjects/maxima_list.html', {'maxima': maxima, 'form': form})


@login_required
@prefet_required
def maxima_delete(request, pk):
    mx = get_object_or_404(Maxima, pk=pk)
    if request.method == 'POST':
        # Vérifier si des matières utilisent ce maxima
        nb = Matiere.objects.filter(maxima=mx.valeur).count()
        if nb:
            messages.error(request, f"Impossible : {nb} matière(s) utilisent MAXIMA {mx.valeur}. "
                                    f"Modifiez-les d'abord.")
            return redirect('maxima_list')
        mx.delete()
        messages.success(request, f"MAXIMA {mx.valeur} supprimé.")
        return redirect('maxima_list')
    return render(request, 'subjects/maxima_confirm_delete.html', {'obj': mx})


# ─── Matières ─────────────────────────────────────────────────────────────────

@login_required
@prefet_required
def matiere_list(request):
    """Liste globale des matières groupées par maxima dynamique."""
    annee = AnneeScolaire.objects.filter(active=True).first()
    matieres = Matiere.objects.prefetch_related('affectations__classe__section')
    grouped = _build_maxima_groups(matieres)

    classes = (
        Classe.objects.filter(annee_scolaire=annee)
            .select_related('section')
            .prefetch_related('matieres__matiere')
        if annee else []
    )

    return render(request, 'subjects/matiere_list.html', {
        'grouped': grouped,
        'classes': classes,
        'annee': annee,
        'total': matieres.count(),
    })


@login_required
@prefet_required
def matiere_create(request):
    form = MatiereForm(request.POST or None)
    if form.is_valid():
        matiere = form.save()
        messages.success(request, f"Matière « {matiere.nom} » créée. Pensez à l'affecter aux classes concernées.")
        return redirect('affectation_list')
    return render(request, 'subjects/matiere_form.html', {'form': form, 'titre': 'Ajouter une matière'})


@login_required
@prefet_required
def matiere_update(request, pk):
    matiere = get_object_or_404(Matiere, pk=pk)
    form = MatiereForm(request.POST or None, instance=matiere)
    if form.is_valid():
        form.save()
        messages.success(request, "Matière modifiée.")
        return redirect('matiere_list')
    return render(request, 'subjects/matiere_form.html', {'form': form, 'titre': 'Modifier la matière', 'obj': matiere})


@login_required
@prefet_required
def matiere_delete(request, pk):
    matiere = get_object_or_404(Matiere, pk=pk)
    if request.method == 'POST':
        matiere.delete()
        messages.success(request, "Matière supprimée.")
        return redirect('matiere_list')
    return render(request, 'subjects/matiere_confirm_delete.html', {'obj': matiere})


# ─── Affectations (vue centrée sur la classe) ──────────────────────────────────

@login_required
@prefet_required
def affectation_list(request):
    """Vue centrée sur la classe : choisir une classe, voir/gérer ses matières."""
    annee = AnneeScolaire.objects.filter(active=True).first()
    classes = (
        Classe.objects.filter(annee_scolaire=annee).select_related('section')
        if annee else Classe.objects.select_related('section')
    )
    classe_id = request.GET.get('classe', '')
    selected_classe = None
    affectations = MatiereClasse.objects.none()
    matieres_disponibles = []  # [{valeur, matieres}]
    maxima_colors = _build_maxima_colors_map()

    if classe_id:
        selected_classe = get_object_or_404(Classe, pk=classe_id)
        affectations = MatiereClasse.objects.filter(
            classe=selected_classe
        ).select_related('matiere', 'enseignant', 'enseignant__user').order_by('matiere__maxima', 'matiere__nom')

        affectees_ids = affectations.values_list('matiere_id', flat=True)
        for i, mx in enumerate(Maxima.objects.all()):
            non_affectees = Matiere.objects.filter(maxima=mx.valeur).exclude(pk__in=affectees_ids)
            if non_affectees.exists():
                matieres_disponibles.append({
                    'valeur': mx.valeur,
                    'matieres': non_affectees,
                    'color': _MAXIMA_COLORS[i % len(_MAXIMA_COLORS)],
                })

    return render(request, 'subjects/affectation_list.html', {
        'classes':              classes,
        'classe_id':            classe_id,
        'selected_classe':      selected_classe,
        'affectations':         affectations,
        'matieres_disponibles': matieres_disponibles,
        'maxima_colors':        maxima_colors,
        'annee':                annee,
    })


@login_required
@prefet_required
def affectation_create(request):
    """Affecter une matière à une classe (+ enseignant optionnel)."""
    classe_id = request.GET.get('classe') or request.POST.get('classe_prefill')
    form = MatiereClasseForm(request.POST or None)

    if classe_id and request.method == 'GET':
        try:
            classe = Classe.objects.get(pk=classe_id)
            form.initial = {'classe': classe}
        except Classe.DoesNotExist:
            pass

    if form.is_valid():
        aff = form.save()
        messages.success(request, f"Matière « {aff.matiere} » affectée à {aff.classe}.")
        return redirect(reverse('affectation_list') + f'?classe={aff.classe.pk}')

    return render(request, 'subjects/affectation_form.html', {
        'form': form,
        'titre': 'Affecter une matière à une classe',
        'classe_prefill': classe_id,
    })


@login_required
@prefet_required
def affectation_rapide(request):
    """Affectation rapide depuis le panneau classe : cocher les matières voulues."""
    if request.method != 'POST':
        return redirect('affectation_list')

    classe_id = request.POST.get('classe_id')
    selected_classe = get_object_or_404(Classe, pk=classe_id)
    matieres_ids = request.POST.getlist('matieres')

    added = 0
    for mid in matieres_ids:
        m = get_object_or_404(Matiere, pk=mid)
        _, created = MatiereClasse.objects.get_or_create(matiere=m, classe=selected_classe)
        if created:
            added += 1

    if added:
        messages.success(request, f"{added} matière(s) ajoutée(s) à {selected_classe}.")
    else:
        messages.info(request, "Aucune nouvelle matière ajoutée (déjà toutes affectées).")
    return redirect(reverse('affectation_list') + f'?classe={classe_id}')


@login_required
@prefet_required
def affectation_update(request, pk):
    aff = get_object_or_404(MatiereClasse, pk=pk)
    form = MatiereClasseForm(request.POST or None, instance=aff)
    if form.is_valid():
        form.save()
        messages.success(request, "Affectation modifiée.")
        return redirect(reverse('affectation_list') + f'?classe={aff.classe.pk}')
    return render(request, 'subjects/affectation_form.html', {
        'form': form,
        'titre': "Modifier l'affectation",
        'obj': aff,
    })


@login_required
@prefet_required
def affectation_delete(request, pk):
    aff = get_object_or_404(MatiereClasse, pk=pk)
    classe_pk = aff.classe.pk
    if request.method == 'POST':
        aff.delete()
        messages.success(request, "Matière retirée de la classe.")
        return redirect(reverse('affectation_list') + f'?classe={classe_pk}')
    return render(request, 'subjects/affectation_confirm_delete.html', {'obj': aff})
