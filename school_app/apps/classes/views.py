from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.views.decorators.http import require_POST
from notifications.service import notify, notify_tous_enseignants, notify_prefets

from .models import AnneeScolaire, Section, Classe, Niveau, DecisionPromotion, JournalOperation, Semestre
from .forms import AnneeScolaireForm, SectionForm, ClasseForm, NiveauForm, DecisionPromotionForm
from accounts.views import prefet_required


# ─── Utilitaires ──────────────────────────────────────────────────────────────

def _suggerer_prochaine_annee(annee_str):
    """À partir de '2024-2025' suggère '2025-2026'."""
    try:
        debut, fin = annee_str.split('-')
        return f"{int(debut)+1}-{int(fin)+1}"
    except Exception:
        return ""


def _verifier_cloture(annee):
    """
    Vérifie les conditions nécessaires à la clôture d'une année scolaire.
    Retourne un dict {ok: bool, checks: [...]} avec le détail de chaque vérification.
    """
    from portail.models import PublicationResultats
    from bulletin.models import ModeleBulletin
    from grades.models import Note

    classes = Classe.objects.filter(annee_scolaire=annee).prefetch_related('eleves', 'matieres')
    checks = []
    tout_ok = True

    # 1. Vérifier que toutes les classes ont des matières affectées
    # Utiliser len(c.matieres.all()) pour bénéficier du prefetch_related (count() force une requête)
    classes_sans_matieres = [c for c in classes if len(c.matieres.all()) == 0]
    ok1 = len(classes_sans_matieres) == 0
    checks.append({
        'titre': "Matières affectées à toutes les classes",
        'ok': ok1,
        'detail': f"{len(classes_sans_matieres)} classe(s) sans matière" if not ok1 else f"{classes.count()} classe(s) configurée(s)",
    })
    if not ok1:
        tout_ok = False

    # 2. Vérifier que les résultats annuels sont publiés pour toutes les classes
    classes_avec_eleves = [c for c in classes if c.eleves.count() > 0]
    pubs_annuelles = set(
        PublicationResultats.objects.filter(
            annee_scolaire=annee, periode='ANNUEL', publie=True
        ).values_list('classe_id', flat=True)
    )
    classes_non_publiees = [c for c in classes_avec_eleves if c.pk not in pubs_annuelles]
    ok2 = len(classes_non_publiees) == 0
    checks.append({
        'titre': "Résultats annuels publiés pour toutes les classes",
        'ok': ok2,
        'detail': (
            f"{len(classes_non_publiees)} classe(s) sans publication annuelle"
            if not ok2 else
            f"{len(classes_avec_eleves)} classe(s) publiée(s)"
        ),
    })
    if not ok2:
        tout_ok = False

    # 3. Vérifier que les bulletins existent pour toutes les classes
    bulletins_classes = set(
        ModeleBulletin.objects.filter(
            annee_scolaire=annee
        ).values_list('classe_id', flat=True)
    )
    classes_sans_bulletin = [c for c in classes_avec_eleves if c.pk not in bulletins_classes]
    ok3 = len(classes_sans_bulletin) == 0
    checks.append({
        'titre': "Modèles de bulletins créés pour toutes les classes",
        'ok': ok3,
        'detail': (
            f"{len(classes_sans_bulletin)} classe(s) sans bulletin"
            if not ok3 else
            f"{len(bulletins_classes)} bulletin(s) créé(s)"
        ),
    })
    if not ok3:
        tout_ok = False

    # 4. Vérifier que toutes les périodes ont des notes pour au moins une classe
    periodes_presentes = set(
        Note.objects.filter(
            matiere_classe__classe__annee_scolaire=annee
        ).values_list('periode', flat=True).distinct()
    )
    periodes_requises = {'1P', '2P', 'EXAM1', '3P', '4P', 'EXAM2'}
    periodes_manquantes = periodes_requises - periodes_presentes
    ok4 = len(periodes_manquantes) == 0
    checks.append({
        'titre': "Toutes les périodes ont des notes saisies",
        'ok': ok4,
        'detail': (
            f"Périodes sans notes : {', '.join(sorted(periodes_manquantes))}"
            if not ok4 else
            "Les 6 périodes + examens ont des notes"
        ),
    })
    if not ok4:
        tout_ok = False

    # 5. Vérifier les décisions de promotion
    total_eleves = sum(len(c.eleves.all()) for c in classes)
    decisions_validees = DecisionPromotion.objects.filter(
        annee_scolaire=annee, validee=True
    ).count()
    ok5 = decisions_validees >= total_eleves
    checks.append({
        'titre': "Décisions de promotion validées pour tous les élèves",
        'ok': ok5,
        'detail': (
            f"{decisions_validees}/{total_eleves} élève(s) avec décision validée"
            if not ok5 else
            f"{decisions_validees} décision(s) validée(s)"
        ),
        'lien': reverse('promotion_eleves', args=[annee.pk]) if not ok5 else None,
    })
    if not ok5:
        tout_ok = False

    return {'ok': tout_ok, 'checks': checks, 'nb_classes': classes.count(), 'nb_eleves': total_eleves}


# ─── Année Scolaire ───────────────────────────────────────────────────────────

@login_required
@prefet_required
def annee_list(request):
    annees = AnneeScolaire.objects.annotate(nb_classes=Count('classes')).all()
    return render(request, 'classes/annee_list.html', {'annees': annees})


@login_required
@prefet_required
def annee_create(request):
    form = AnneeScolaireForm(request.POST or None)
    if form.is_valid():
        annee = form.save()
        JournalOperation.objects.create(
            type_operation='CREATION_ANNEE',
            annee_scolaire=annee,
            utilisateur=request.user,
            details={'annee': annee.annee},
        )
        messages.success(request, f"Année scolaire {annee} créée.")
        return redirect('annee_list')
    return render(request, 'classes/annee_form.html', {'form': form, 'titre': "Ajouter une année scolaire"})


@login_required
@prefet_required
def annee_update(request, pk):
    annee = get_object_or_404(AnneeScolaire, pk=pk)
    if annee.cloturee:
        messages.error(request, "Impossible de modifier une année clôturée.")
        return redirect('annee_list')
    form = AnneeScolaireForm(request.POST or None, instance=annee)
    if form.is_valid():
        form.save()
        messages.success(request, "Année scolaire modifiée.")
        return redirect('annee_list')
    return render(request, 'classes/annee_form.html', {'form': form, 'titre': "Modifier l'année scolaire", 'obj': annee})


@login_required
@prefet_required
def annee_delete(request, pk):
    annee = get_object_or_404(AnneeScolaire, pk=pk)
    if annee.active or annee.cloturee:
        messages.error(request, "Impossible de supprimer l'année active ou une année clôturée.")
        return redirect('annee_list')
    if request.method == 'POST':
        annee.delete()
        messages.success(request, "Année scolaire supprimée.")
        return redirect('annee_list')
    return render(request, 'classes/confirm_delete.html', {'obj': annee, 'type': 'année scolaire'})


@login_required
@prefet_required
def annee_activer(request, pk):
    """Rendre une année active (désactive toutes les autres)."""
    annee = get_object_or_404(AnneeScolaire, pk=pk)
    if annee.cloturee:
        messages.error(request, "Impossible d'activer une année clôturée.")
        return redirect('annee_list')
    if request.method == 'POST':
        annee.active = True
        annee.save()
        JournalOperation.objects.create(
            type_operation='ACTIVATION_ANNEE',
            annee_scolaire=annee,
            utilisateur=request.user,
            details={'annee': annee.annee},
        )
        messages.success(request, f"Année {annee} activée avec succès.")
        notify_tous_enseignants(
            f"Nouvelle année scolaire activée : {annee}",
            "Vous pouvez désormais saisir les notes pour cette année scolaire.",
            categorie='SCOLAIRE', priorite='IMPORTANT', type_notif='ANNEE_ACTIVEE',
            lien='/classes/', expediteur=request.user, annee=annee,
        )
    return redirect('annee_list')


@login_required
@prefet_required
def cloture_annee(request, pk):
    """Assistant de clôture d'une année scolaire."""
    annee = get_object_or_404(AnneeScolaire, pk=pk)

    if annee.cloturee:
        messages.info(request, f"L'année {annee} est déjà clôturée.")
        return redirect('annee_list')

    verification = _verifier_cloture(annee)
    force_cloture = request.GET.get('force') == '1'

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'cloturer':
            if not verification['ok'] and not force_cloture:
                messages.error(request, "Des anomalies ont été détectées. Corrigez-les ou utilisez la clôture forcée.")
            else:
                with transaction.atomic():
                    annee.cloturer(user=request.user)
                    messages.success(
                        request,
                        f"✅ Année {annee} clôturée avec succès. Elle est maintenant en lecture seule."
                    )
                return redirect('annee_list')

    return render(request, 'classes/cloture_annee.html', {
        'annee': annee,
        'verification': verification,
        'force_cloture': force_cloture,
    })


@login_required
@prefet_required
def promotion_eleves(request, pk):
    """Assistant de promotion des élèves pour une année scolaire."""
    annee = get_object_or_404(AnneeScolaire, pk=pk)
    annee_active = AnneeScolaire.objects.filter(active=True).exclude(pk=pk).first()

    # Récupérer toutes les classes de l'année avec leurs élèves
    classes = Classe.objects.filter(
        annee_scolaire=annee
    ).select_related('section', 'niveau').prefetch_related('eleves').order_by('niveau__ordre', 'nom')

    # Classes cibles (pour l'année active ou toute autre année non-clôturée)
    annees_cibles = AnneeScolaire.objects.filter(cloturee=False).exclude(pk=pk)
    classes_cibles = []
    if annees_cibles.exists():
        classes_cibles = list(
            Classe.objects.filter(
                annee_scolaire__in=annees_cibles
            ).select_related('section', 'niveau', 'annee_scolaire').order_by(
                'annee_scolaire__annee', 'niveau__ordre', 'nom'
            )
        )

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'sauvegarder':
            nb_sauvegardees = 0
            nb_validees = 0
            with transaction.atomic():
                for classe in classes:
                    for eleve in classe.eleves.all():
                        decision_val = request.POST.get(f'decision_{eleve.pk}', 'ADMIS')
                        destination_id = request.POST.get(f'destination_{eleve.pk}', '') or None
                        observations = request.POST.get(f'obs_{eleve.pk}', '')
                        valider = request.POST.get(f'valider_{eleve.pk}') == '1'

                        decision, created = DecisionPromotion.objects.update_or_create(
                            eleve=eleve,
                            annee_scolaire=annee,
                            defaults={
                                'classe_source': classe,
                                'decision': decision_val,
                                'classe_destination_id': destination_id,
                                'observations': observations,
                                'validee': valider,
                                'decidee_par': request.user,
                            }
                        )
                        nb_sauvegardees += 1
                        if valider:
                            nb_validees += 1

            JournalOperation.objects.create(
                type_operation='PROMOTION',
                annee_scolaire=annee,
                utilisateur=request.user,
                details={
                    'annee': annee.annee,
                    'nb_decisions': nb_sauvegardees,
                    'nb_validees': nb_validees,
                },
            )
            messages.success(request, f"✅ {nb_sauvegardees} décision(s) sauvegardée(s), {nb_validees} validée(s).")
            return redirect('promotion_eleves', pk=pk)

        elif action == 'appliquer_promotions':
            # Appliquer les décisions validées : déplacer les élèves vers leurs nouvelles classes
            decisions_admis = DecisionPromotion.objects.filter(
                annee_scolaire=annee,
                validee=True,
                decision='ADMIS',
                classe_destination__isnull=False,
            ).select_related('eleve', 'classe_destination')

            nb_deplace = 0
            with transaction.atomic():
                for decision in decisions_admis:
                    decision.eleve.classe = decision.classe_destination
                    decision.eleve.save(update_fields=['classe'])
                    nb_deplace += 1

            JournalOperation.objects.create(
                type_operation='PROMOTION',
                annee_scolaire=annee,
                utilisateur=request.user,
                details={
                    'annee': annee.annee,
                    'action': 'application',
                    'nb_deplace': nb_deplace,
                },
            )
            messages.success(request, f"✅ {nb_deplace} élève(s) déplacé(s) vers leur nouvelle classe.")
            return redirect('promotion_eleves', pk=pk)

    # Récupérer les décisions existantes
    decisions_existantes = {
        d.eleve_id: d
        for d in DecisionPromotion.objects.filter(annee_scolaire=annee).select_related('classe_destination')
    }

    lignes = []
    for classe in classes:
        for eleve in classe.eleves.all():
            decision = decisions_existantes.get(eleve.pk)
            # Auto-suggestion du niveau suivant
            niveau_suivant = classe.niveau.get_niveau_suivant() if classe.niveau else None
            lignes.append({
                'eleve': eleve,
                'classe': classe,
                'decision': decision,
                'niveau_suivant': niveau_suivant,
            })

    nb_valides = sum(1 for d in decisions_existantes.values() if d.validee)

    return render(request, 'classes/promotion_eleves.html', {
        'annee': annee,
        'lignes': lignes,
        'classes_cibles': classes_cibles,
        'annees_cibles': annees_cibles,
        'decision_choices': DecisionPromotion.DECISION_CHOICES,
        'nb_valides': nb_valides,
        'nb_total': len(lignes),
    })


@login_required
@prefet_required
def journal_operations(request):
    """Journal des opérations sur les années scolaires."""
    annee_id = request.GET.get('annee', '')
    operations = JournalOperation.objects.select_related('annee_scolaire', 'utilisateur').all()
    if annee_id:
        operations = operations.filter(annee_scolaire_id=annee_id)
    annees = AnneeScolaire.objects.all()
    return render(request, 'classes/journal_operations.html', {
        'operations': operations,
        'annees': annees,
        'annee_id': annee_id,
    })


@login_required
@prefet_required
def reconduire_annee(request, pk):
    """
    Reconduction d'une année scolaire vers une nouvelle :
    - Recopie les classes (même nom/section/niveau, nouvelle année)
    - Recopie les affectations matières/enseignants par classe
    - Déplace les élèves vers leurs nouvelles classes
    - Notes et bulletins : fresh start
    """
    source_annee = get_object_or_404(AnneeScolaire, pk=pk)
    toutes_annees = AnneeScolaire.objects.exclude(pk=pk).filter(cloturee=False).order_by('-annee')

    classes_source = Classe.objects.filter(
        annee_scolaire=source_annee
    ).select_related('section', 'niveau').prefetch_related('matieres__matiere', 'matieres__enseignant', 'eleves')

    apercu = []
    for c in classes_source:
        apercu.append({
            'classe': c,
            'nb_matieres': c.matieres.count(),
            'nb_eleves': c.eleves.count(),
        })

    if request.method == 'POST':
        nouvelle_annee_str = request.POST.get('nouvelle_annee', '').strip()
        target_pk = request.POST.get('annee_existante', '')
        copier_matieres = request.POST.get('copier_matieres') == '1'
        copier_eleves = request.POST.get('copier_eleves') == '1'
        activer = request.POST.get('activer_nouvelle') == '1'

        # ── Obtenir ou créer la nouvelle année ──
        if target_pk:
            target_annee = get_object_or_404(AnneeScolaire, pk=target_pk)
        elif nouvelle_annee_str:
            if AnneeScolaire.objects.filter(annee=nouvelle_annee_str).exists():
                messages.error(request, f"L'année «{nouvelle_annee_str}» existe déjà. Sélectionnez-la dans la liste.")
                return redirect(request.path)
            target_annee = AnneeScolaire.objects.create(annee=nouvelle_annee_str, active=False)
            JournalOperation.objects.create(
                type_operation='CREATION_ANNEE',
                annee_scolaire=target_annee,
                utilisateur=request.user,
                details={'annee': nouvelle_annee_str, 'source': source_annee.annee},
            )
        else:
            messages.error(request, "Indiquez une nouvelle année scolaire.")
            return redirect(request.path)

        stats = {'classes': 0, 'matieres': 0, 'eleves': 0, 'ignorees': 0}

        try:
            with transaction.atomic():
                for c in classes_source:
                    new_classe, created = Classe.objects.get_or_create(
                        nom=c.nom,
                        section=c.section,
                        annee_scolaire=target_annee,
                        defaults={'niveau': c.niveau},
                    )
                    if created:
                        stats['classes'] += 1
                    else:
                        # Mettre à jour le niveau si la classe existait déjà
                        if new_classe.niveau != c.niveau:
                            new_classe.niveau = c.niveau
                            new_classe.save(update_fields=['niveau'])
                        stats['ignorees'] += 1

                    if copier_matieres:
                        from subjects.models import MatiereClasse
                        for mc in c.matieres.select_related('matiere', 'enseignant'):
                            _, mc_created = MatiereClasse.objects.get_or_create(
                                matiere=mc.matiere,
                                classe=new_classe,
                                defaults={'enseignant': mc.enseignant}
                            )
                            if mc_created:
                                stats['matieres'] += 1

                    if copier_eleves:
                        # Utiliser les décisions de promotion si disponibles
                        decisions_map = {
                            d.eleve_id: d
                            for d in DecisionPromotion.objects.filter(
                                annee_scolaire=source_annee,
                                classe_source=c,
                                validee=True,
                            ).select_related('classe_destination')
                        }
                        for eleve in c.eleves.all():
                            decision = decisions_map.get(eleve.pk)
                            if decision and decision.decision == 'ADMIS' and decision.classe_destination:
                                # Promouvoir vers la classe de destination
                                eleve.classe = decision.classe_destination
                            elif decision and decision.decision in ('TRANSFERE', 'DIPLOME'):
                                # Ne pas déplacer (archivé ou transféré)
                                continue
                            else:
                                # Par défaut : déplacer vers la même classe dans la nouvelle année
                                eleve.classe = new_classe
                            eleve.save(update_fields=['classe'])
                            stats['eleves'] += 1

                if activer:
                    target_annee.active = True
                    target_annee.save()
                    JournalOperation.objects.create(
                        type_operation='ACTIVATION_ANNEE',
                        annee_scolaire=target_annee,
                        utilisateur=request.user,
                        details={'annee': target_annee.annee},
                    )

            JournalOperation.objects.create(
                type_operation='MIGRATION',
                annee_scolaire=target_annee,
                utilisateur=request.user,
                details={
                    'source': source_annee.annee,
                    'destination': target_annee.annee,
                    'stats': stats,
                },
            )

        except Exception as e:
            messages.error(request, f"Erreur lors de la reconduction : {e}")
            return redirect(request.path)

        msg_parts = [f"{stats['classes']} classe(s) créée(s)"]
        if copier_matieres:
            msg_parts.append(f"{stats['matieres']} affectation(s) matières copiée(s)")
        if copier_eleves:
            msg_parts.append(f"{stats['eleves']} élève(s) déplacé(s)")
        if stats['ignorees']:
            msg_parts.append(f"{stats['ignorees']} classe(s) déjà existante(s) ignorée(s)")

        messages.success(
            request,
            f"✅ Reconduction vers {target_annee} terminée : {', '.join(msg_parts)}. "
            f"Les notes et bulletins repartent de zéro pour la nouvelle année."
        )
        return redirect('annee_list')

    suggestion = _suggerer_prochaine_annee(source_annee.annee)
    return render(request, 'classes/reconduire_annee.html', {
        'source_annee': source_annee,
        'toutes_annees': toutes_annees,
        'apercu': apercu,
        'suggestion': suggestion,
    })


# ─── Niveau ───────────────────────────────────────────────────────────────────

@login_required
@prefet_required
def niveau_list(request):
    niveaux = Niveau.objects.annotate(nb_classes=Count('classes')).all()
    return render(request, 'classes/niveau_list.html', {'niveaux': niveaux})


@login_required
@prefet_required
def niveau_create(request):
    form = NiveauForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Niveau créé.")
        return redirect('niveau_list')
    return render(request, 'classes/niveau_form.html', {'form': form, 'titre': 'Ajouter un niveau'})


@login_required
@prefet_required
def niveau_update(request, pk):
    niveau = get_object_or_404(Niveau, pk=pk)
    form = NiveauForm(request.POST or None, instance=niveau)
    if form.is_valid():
        form.save()
        messages.success(request, "Niveau modifié.")
        return redirect('niveau_list')
    return render(request, 'classes/niveau_form.html', {'form': form, 'titre': 'Modifier le niveau', 'obj': niveau})


@login_required
@prefet_required
def niveau_delete(request, pk):
    niveau = get_object_or_404(Niveau, pk=pk)
    if request.method == 'POST':
        niveau.delete()
        messages.success(request, "Niveau supprimé.")
        return redirect('niveau_list')
    return render(request, 'classes/confirm_delete.html', {'obj': niveau, 'type': 'niveau'})


# ─── Section ──────────────────────────────────────────────────────────────────

@login_required
@prefet_required
def section_list(request):
    sections = Section.objects.all()
    return render(request, 'classes/section_list.html', {'sections': sections})


@login_required
@prefet_required
def section_create(request):
    form = SectionForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Section créée.")
        return redirect('section_list')
    return render(request, 'classes/section_form.html', {'form': form, 'titre': 'Ajouter une section'})


@login_required
@prefet_required
def section_update(request, pk):
    section = get_object_or_404(Section, pk=pk)
    form = SectionForm(request.POST or None, instance=section)
    if form.is_valid():
        form.save()
        messages.success(request, "Section modifiée.")
        return redirect('section_list')
    return render(request, 'classes/section_form.html', {'form': form, 'titre': 'Modifier la section', 'obj': section})


@login_required
@prefet_required
def section_delete(request, pk):
    section = get_object_or_404(Section, pk=pk)
    if request.method == 'POST':
        section.delete()
        messages.success(request, "Section supprimée.")
        return redirect('section_list')
    return render(request, 'classes/confirm_delete.html', {'obj': section, 'type': 'section'})


# ─── Classe ───────────────────────────────────────────────────────────────────

@login_required
def classe_list(request):
    annee    = AnneeScolaire.objects.filter(active=True).first()
    annee_id = request.GET.get('annee', annee.pk if annee else None)
    classes  = Classe.objects.select_related('section', 'annee_scolaire', 'niveau')
    if annee_id:
        classes = classes.filter(annee_scolaire_id=annee_id)
    annees = AnneeScolaire.objects.all()
    return render(request, 'classes/classe_list.html', {
        'classes': classes, 'annees': annees, 'annee_id': str(annee_id) if annee_id else ''
    })


@login_required
@prefet_required
def classe_create(request):
    form = ClasseForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Classe créée.")
        return redirect('classe_list')
    return render(request, 'classes/classe_form.html', {'form': form, 'titre': 'Créer une classe'})


@login_required
@prefet_required
def classe_update(request, pk):
    classe = get_object_or_404(Classe, pk=pk)
    if not classe.est_modifiable:
        messages.error(request, "Impossible de modifier une classe d'une année clôturée.")
        return redirect('classe_list')
    form = ClasseForm(request.POST or None, instance=classe)
    if form.is_valid():
        form.save()
        messages.success(request, "Classe modifiée.")
        return redirect('classe_list')
    return render(request, 'classes/classe_form.html', {'form': form, 'titre': 'Modifier la classe', 'obj': classe})


@login_required
@prefet_required
def classe_delete(request, pk):
    classe = get_object_or_404(Classe, pk=pk)
    if not classe.est_modifiable:
        messages.error(request, "Impossible de supprimer une classe d'une année clôturée.")
        return redirect('classe_list')
    if request.method == 'POST':
        classe.delete()
        messages.success(request, "Classe supprimée.")
        return redirect('classe_list')
    return render(request, 'classes/confirm_delete.html', {'obj': classe, 'type': 'classe'})


# ─── Gestion des semestres ────────────────────────────────────────────────────

@login_required
@prefet_required
def semestre_list(request):
    """Liste et gestion des semestres pour l'année scolaire active."""
    try:
        annee = AnneeScolaire.objects.get(active=True)
    except AnneeScolaire.DoesNotExist:
        messages.warning(request, "Aucune année scolaire active. Activez d'abord une année.")
        return redirect('annee_list')
    semestres = annee.semestres.all()
    return render(request, 'classes/semestre_list.html', {
        'annee':     annee,
        'semestres': semestres,
        's1':        semestres.filter(numero=1).first(),
        's2':        semestres.filter(numero=2).first(),
    })


@login_required
@prefet_required
@require_POST
def semestre_initialiser(request, annee_pk):
    """Crée S1 et S2 pour l'année donnée s'ils n'existent pas."""
    annee = get_object_or_404(AnneeScolaire, pk=annee_pk, cloturee=False)
    created = 0
    for numero in [1, 2]:
        _, c = Semestre.objects.get_or_create(annee_scolaire=annee, numero=numero)
        if c:
            created += 1
    if created:
        messages.success(request, f"{created} semestre(s) initialisé(s) pour {annee}.")
    else:
        messages.info(request, "Les semestres sont déjà initialisés.")
    return redirect('semestre_list')


@login_required
@prefet_required
@require_POST
def semestre_activer(request, pk):
    """BROUILLON → ACTIF. Un seul semestre actif à la fois par année."""
    semestre = get_object_or_404(Semestre, pk=pk)
    annee    = semestre.annee_scolaire

    if semestre.statut != 'BROUILLON':
        messages.error(request, "Seul un semestre en état Brouillon peut être activé.")
        return redirect('semestre_list')
    if annee.semestres.filter(statut='ACTIF').exists():
        messages.error(request, "Un semestre est déjà actif. Publiez-le d'abord avant d'en activer un autre.")
        return redirect('semestre_list')
    if semestre.numero == 2:
        s1 = annee.semestres.filter(numero=1).first()
        if s1 and s1.statut not in ('PUBLIE', 'ARCHIVE'):
            messages.error(request, "Le Premier semestre doit être publié avant d'activer le Deuxième semestre.")
            return redirect('semestre_list')

    semestre.statut          = 'ACTIF'
    semestre.date_activation = timezone.now()
    semestre.save()
    JournalOperation.objects.create(
        type_operation='ACTIVATION_SEMESTRE',
        annee_scolaire=annee,
        utilisateur=request.user,
        details={'semestre': semestre.numero},
    )
    messages.success(request, f"{semestre.get_numero_display()} activé avec succès.")
    notify_tous_enseignants(
        f"{semestre.get_numero_display()} activé — saisie des notes ouverte",
        f"Périodes disponibles : {', '.join(semestre.periodes)}.",
        categorie='SCOLAIRE', priorite='IMPORTANT', type_notif='SEMESTRE_ACTIF',
        lien='/notes/', expediteur=request.user, annee=annee,
    )
    return redirect('semestre_list')


@login_required
@prefet_required
@require_POST
def semestre_publier(request, pk):
    """ACTIF → PUBLIE — verrouille les notes de toutes les périodes du semestre."""
    semestre = get_object_or_404(Semestre, pk=pk)

    if semestre.statut != 'ACTIF':
        messages.error(request, "Seul un semestre actif peut être publié.")
        return redirect('semestre_list')

    semestre.statut           = 'PUBLIE'
    semestre.date_publication = timezone.now()
    semestre.publie_par       = request.user
    semestre.save()
    JournalOperation.objects.create(
        type_operation='PUBLICATION_SEMESTRE',
        annee_scolaire=semestre.annee_scolaire,
        utilisateur=request.user,
        details={'semestre': semestre.numero, 'periodes': semestre.periodes},
    )
    messages.success(request, f"{semestre.get_numero_display()} publié — les notes sont désormais verrouillées.")
    notify_tous_enseignants(
        f"{semestre.get_numero_display()} publié — notes verrouillées",
        "Les notes de ce semestre sont en lecture seule. Consultez l'historique pour les voir.",
        categorie='SCOLAIRE', priorite='AVERT', type_notif='SEMESTRE_PUBLIE',
        lien='/notes/historique/', expediteur=request.user, annee=semestre.annee_scolaire,
    )
    return redirect('semestre_list')


@login_required
@prefet_required
@require_POST
def semestre_archiver(request, pk):
    """PUBLIE → ARCHIVE."""
    semestre = get_object_or_404(Semestre, pk=pk)

    if semestre.statut != 'PUBLIE':
        messages.error(request, "Seul un semestre publié peut être archivé.")
        return redirect('semestre_list')

    semestre.statut         = 'ARCHIVE'
    semestre.date_archivage = timezone.now()
    semestre.save()
    messages.success(request, f"{semestre.get_numero_display()} archivé.")
    notify_prefets(
        f"{semestre.get_numero_display()} archivé",
        f"Les données du {semestre.get_numero_display().lower()} sont conservées en lecture seule.",
        categorie='SCOLAIRE', priorite='INFO', type_notif='SEMESTRE_ARCHIVE',
        lien='/classes/semestres/', expediteur=request.user, annee=semestre.annee_scolaire,
    )
    return redirect('semestre_list')


@login_required
@prefet_required
@require_POST
def semestre_toggle_repechage(request, pk):
    """Activer/désactiver le repêchage pour le Deuxième semestre."""
    semestre = get_object_or_404(Semestre, pk=pk, numero=2)

    if semestre.statut != 'ACTIF':
        messages.error(request, "Le repêchage ne peut être modifié que sur un semestre actif.")
        return redirect('semestre_list')

    semestre.repechage_actif = not semestre.repechage_actif
    semestre.save()
    etat = "activé" if semestre.repechage_actif else "désactivé"
    messages.success(request, f"Repêchage {etat}.")
    notify_tous_enseignants(
        f"Repêchage {etat} — {semestre.get_numero_display()}",
        "La période de repêchage a été mise à jour pour le deuxième semestre.",
        categorie='SCOLAIRE', priorite='INFO',
        type_notif='REPECHAGE_ACTIF' if semestre.repechage_actif else 'REPECHAGE_INACTIF',
        lien='/notes/', expediteur=request.user, annee=semestre.annee_scolaire,
    )
    return redirect('semestre_list')
