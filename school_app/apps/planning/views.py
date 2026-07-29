from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q

from accounts.views import prefet_or_secretariat_required
from classes.models import AnneeScolaire, Classe
from subjects.models import MatiereClasse
from teachers.models import Teacher

from .models import Salle, CreneauHoraire, SeanceHoraire
from .forms import SalleForm, CreneauHoraireForm, SeanceHoraireForm


# ─── Salles ───────────────────────────────────────────────────────────────────

@login_required
@prefet_or_secretariat_required
def salle_list(request):
    salles = Salle.objects.all()
    form = SalleForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Salle ajoutée.")
        return redirect('salle_list')
    return render(request, 'planning/salle_list.html', {'salles': salles, 'form': form})


@login_required
@prefet_or_secretariat_required
def salle_update(request, pk):
    salle = get_object_or_404(Salle, pk=pk)
    form = SalleForm(request.POST or None, instance=salle)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Salle modifiée.")
        return redirect('salle_list')
    return render(request, 'planning/salle_form.html', {'form': form, 'obj': salle, 'titre': 'Modifier la salle'})


@login_required
@prefet_or_secretariat_required
def salle_delete(request, pk):
    salle = get_object_or_404(Salle, pk=pk)
    if request.method == 'POST':
        salle.delete()
        messages.success(request, "Salle supprimée.")
        return redirect('salle_list')
    return render(request, 'planning/salle_confirm_delete.html', {'obj': salle})


# ─── Créneaux ─────────────────────────────────────────────────────────────────

@login_required
@prefet_or_secretariat_required
def creneau_list(request):
    creneaux = CreneauHoraire.objects.all()
    form = CreneauHoraireForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            obj = form.save(commit=False)
            obj.full_clean()
            obj.save()
            messages.success(request, "Créneau ajouté.")
            return redirect('creneau_list')
        except ValidationError as e:
            for field, errs in (e.message_dict.items() if hasattr(e, 'message_dict') else [('__all__', e.messages)]):
                for err in errs:
                    form.add_error(field if field != '__all__' else None, err)
    return render(request, 'planning/creneau_list.html', {'creneaux': creneaux, 'form': form})


@login_required
@prefet_or_secretariat_required
def creneau_delete(request, pk):
    creneau = get_object_or_404(CreneauHoraire, pk=pk)
    if request.method == 'POST':
        creneau.delete()
        messages.success(request, "Créneau supprimé.")
        return redirect('creneau_list')
    return render(request, 'planning/creneau_confirm_delete.html', {'obj': creneau})


# ─── Planning principal (vue hebdomadaire) ─────────────────────────────────────

@login_required
@prefet_or_secretariat_required
def planning_list(request):
    """Vue hebdomadaire — filtrable par classe ou enseignant."""
    annee = AnneeScolaire.objects.filter(active=True).first()
    annee_id = request.GET.get('annee', annee.pk if annee else None)
    classe_id = request.GET.get('classe')
    enseignant_id = request.GET.get('enseignant')

    annees = AnneeScolaire.objects.order_by('-annee')
    classes = Classe.objects.filter(annee_scolaire_id=annee_id).select_related('section') if annee_id else []
    enseignants = Teacher.objects.select_related('user').order_by('user__last_name')

    seances = SeanceHoraire.objects.filter(
        annee_scolaire_id=annee_id
    ).select_related(
        'creneau', 'matiere_classe__matiere', 'matiere_classe__classe',
        'matiere_classe__classe__section', 'matiere_classe__enseignant__user', 'salle'
    ) if annee_id else SeanceHoraire.objects.none()

    if classe_id:
        seances = seances.filter(matiere_classe__classe_id=classe_id)
    if enseignant_id:
        seances = seances.filter(matiere_classe__enseignant_id=enseignant_id)

    # Organiser en grille jour → créneau → séances
    jours = list(range(1, 7))  # 1=Lundi … 6=Samedi
    tous_creneaux = CreneauHoraire.objects.order_by('heure_debut', 'heure_fin', 'jour')

    # Plages horaires uniques (pour les lignes du tableau)
    seen_times = set()
    time_slots = []
    for c in tous_creneaux:
        key = (c.heure_debut, c.heure_fin)
        if key not in seen_times:
            seen_times.add(key)
            time_slots.append(c)   # on garde un objet représentatif

    # Grille : {(heure_debut, heure_fin): {jour: {'seances': [...], 'creneau': obj}}}
    grille_table = _build_grille_table(seances, tous_creneaux, jours)

    return render(request, 'planning/planning_list.html', {
        'annees': annees,
        'annee_id': str(annee_id) if annee_id else '',
        'classes': classes,
        'enseignants': enseignants,
        'classe_id': str(classe_id) if classe_id else '',
        'enseignant_id': str(enseignant_id) if enseignant_id else '',
        'grille_table': grille_table,
        'time_slots': time_slots,
        'jours': jours,
        'JOURS_LABELS': {1:'Lundi',2:'Mardi',3:'Mercredi',4:'Jeudi',5:'Vendredi',6:'Samedi'},
        'nb_seances': seances.count(),
        'annee_active': annee,
        'annee_id_for_new': annee_id,
    })


def _build_grille(seances, creneaux, jours):
    """Retourne {jour: {creneau_pk: [seance, ...]}} pour le template."""
    grille = {j: {} for j in jours}
    for s in seances:
        j = s.creneau.jour
        c = s.creneau.pk
        grille.setdefault(j, {}).setdefault(c, []).append(s)
    return grille


def _build_grille_table(seances, tous_creneaux, jours):
    """
    Retourne une liste de lignes pour le tableau hebdomadaire.
    Chaque ligne : {heure_debut, heure_fin, libelle, type_creneau, is_repos, cells:{jour: {creneau, seances, is_repos}}}
    """
    # Index séances par creneau_pk
    seances_by_creneau = {}
    for s in seances:
        seances_by_creneau.setdefault(s.creneau_id, []).append(s)

    # Index creneaux par jour → {(hd, hf): obj}
    creneau_index = {}
    for c in tous_creneaux:
        creneau_index.setdefault(c.jour, {})[(c.heure_debut, c.heure_fin)] = c

    # Plages horaires uniques (dans l'ordre)
    seen = set()
    time_keys = []
    for c in tous_creneaux:
        k = (c.heure_debut, c.heure_fin)
        if k not in seen:
            seen.add(k)
            time_keys.append(k)

    rows = []
    for hd, hf in time_keys:
        # Créneau représentatif pour libellé / type
        repr_c = None
        for j in jours:
            repr_c = creneau_index.get(j, {}).get((hd, hf))
            if repr_c:
                break

        type_c = repr_c.type_creneau if repr_c else 'cours'
        libelle = (repr_c.libelle if repr_c and repr_c.libelle
                   else "%s–%s" % (hd.strftime('%Hh%M'), hf.strftime('%Hh%M')))

        cells = {}
        for j in jours:
            c = creneau_index.get(j, {}).get((hd, hf))
            cells[j] = {
                'creneau': c,
                'seances': seances_by_creneau.get(c.pk, []) if c else [],
                'is_repos': (c.type_creneau != 'cours') if c else False,
                'type_display': c.get_type_creneau_display() if c else '',
                'creneau_pk': c.pk if c else None,
            }

        rows.append({
            'heure_debut': hd,
            'heure_fin':   hf,
            'libelle':     libelle,
            'type_creneau': type_c,
            'is_repos':    type_c != 'cours',
            'cells':       cells,
        })

    return rows


# ─── Séances (CRUD) ───────────────────────────────────────────────────────────

@login_required
@prefet_or_secretariat_required
def seance_create(request):
    annee = AnneeScolaire.objects.filter(active=True).first()
    form = SeanceHoraireForm(
        request.POST or None,
        annee_scolaire=annee,
        initial={'annee_scolaire': annee},
    )
    if request.method == 'POST' and form.is_valid():
        try:
            obj = form.save(commit=False)
            obj.full_clean()
            obj.save()
            messages.success(request, "Séance ajoutée au planning.")
            return redirect('planning_list')
        except ValidationError as e:
            _add_validation_errors(form, e)
    return render(request, 'planning/seance_form.html', {
        'form': form,
        'titre': 'Ajouter une séance',
    })


@login_required
@prefet_or_secretariat_required
def seance_update(request, pk):
    seance = get_object_or_404(SeanceHoraire, pk=pk)
    form = SeanceHoraireForm(
        request.POST or None,
        instance=seance,
        annee_scolaire=seance.annee_scolaire,
    )
    if request.method == 'POST' and form.is_valid():
        try:
            obj = form.save(commit=False)
            obj.full_clean()
            obj.save()
            messages.success(request, "Séance modifiée.")
            return redirect('planning_list')
        except ValidationError as e:
            _add_validation_errors(form, e)
    return render(request, 'planning/seance_form.html', {
        'form': form,
        'titre': 'Modifier la séance',
        'obj': seance,
    })


@login_required
@prefet_or_secretariat_required
def seance_delete(request, pk):
    seance = get_object_or_404(SeanceHoraire, pk=pk)
    if request.method == 'POST':
        seance.delete()
        messages.success(request, "Séance supprimée.")
        return redirect('planning_list')
    return render(request, 'planning/seance_confirm_delete.html', {'obj': seance})


# ─── Planning enseignant (son propre planning uniquement) ─────────────────────

@login_required
def mon_planning(request):
    """Un enseignant consulte uniquement son propre planning."""
    if not request.user.is_enseignant():
        messages.error(request, "Cette page est réservée aux enseignants.")
        return redirect('dashboard')

    try:
        teacher = request.user.teacher_profile
    except Exception:
        messages.error(request, "Profil enseignant introuvable.")
        return redirect('dashboard')

    annee = AnneeScolaire.objects.filter(active=True).first()
    annee_id = request.GET.get('annee', annee.pk if annee else None)

    seances = SeanceHoraire.objects.filter(
        matiere_classe__enseignant=teacher,
        annee_scolaire_id=annee_id,
    ).select_related(
        'creneau', 'matiere_classe__matiere',
        'matiere_classe__classe', 'matiere_classe__classe__section', 'salle'
    ).order_by('creneau__jour', 'creneau__heure_debut') if annee_id else []

    jours = list(range(1, 7))
    creneaux = CreneauHoraire.objects.order_by('jour', 'heure_debut')
    grille = _build_grille(seances, creneaux, jours)

    # Prochains cours (aujourd'hui et à venir)
    from datetime import date
    aujourd_hui_num = date.today().isoweekday()  # 1=Lundi ... 7=Dimanche
    prochains = [s for s in seances if s.creneau.jour >= min(aujourd_hui_num, 6)][:5]

    annees = AnneeScolaire.objects.order_by('-annee')

    return render(request, 'planning/mon_planning.html', {
        'seances': seances,
        'grille': grille,
        'jours': jours,
        'JOURS_LABELS': {1:'Lundi',2:'Mardi',3:'Mercredi',4:'Jeudi',5:'Vendredi',6:'Samedi'},
        'prochains': prochains,
        'annee_active': annee,
        'annees': annees,
        'annee_id': str(annee_id) if annee_id else '',
        'teacher': teacher,
    })


# ─── Utilitaire ───────────────────────────────────────────────────────────────

def _add_validation_errors(form, exc):
    if hasattr(exc, 'message_dict'):
        for field, errs in exc.message_dict.items():
            for err in errs:
                form.add_error(field if field in form.fields else None, err)
    else:
        for msg in exc.messages:
            form.add_error(None, msg)
