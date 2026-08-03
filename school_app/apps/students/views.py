from urllib.parse import urlencode
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse
from django.urls import reverse
from .models import Student, Tuteur
from .forms import StudentForm, TuteurForm
from accounts.views import prefet_required, prefet_or_secretariat_required

PER_PAGE = 20


def _redirect_to_exact_page(request, ordered_qs, exact_qs, page_size, url_name, extra_params=None):
    q = request.GET.get('q', '').strip()
    if not q or request.GET.get('page'):
        return None
    if exact_qs.count() != 1:
        return None

    exact_obj = exact_qs.first()
    ordered_ids = list(ordered_qs.values_list('pk', flat=True))
    if exact_obj is None or exact_obj.pk not in ordered_ids:
        return None

    target_page = (ordered_ids.index(exact_obj.pk) // page_size) + 1
    params = {'q': q, 'page': target_page}
    if extra_params:
        params.update(extra_params)
    return redirect(f"{reverse(url_name)}?{urlencode(params)}")


# ── Élèves ────────────────────────────────────────────────────────────────────

@login_required
@prefet_or_secretariat_required
def student_list(request):
    q = request.GET.get('q', '').strip()
    classe_id = request.GET.get('classe', '')
    students = Student.objects.select_related('classe', 'classe__section', 'tuteur')
    if q:
        students = students.filter(
            Q(nom__icontains=q) | Q(postnom__icontains=q) |
            Q(prenom__icontains=q) | Q(matricule__icontains=q)
        )
    if classe_id:
        students = students.filter(classe_id=classe_id)

    ordered_students = students.order_by('nom', 'postnom', 'prenom', 'matricule', 'pk')
    redirect_response = _redirect_to_exact_page(
        request,
        ordered_students,
        Student.objects.filter(
            Q(nom__iexact=q) | Q(postnom__iexact=q) |
            Q(prenom__iexact=q) | Q(matricule__iexact=q)
        ),
        PER_PAGE,
        'student_list',
        {'classe': classe_id} if classe_id else None,
    )
    if redirect_response is not None:
        return redirect_response

    from classes.models import Classe, AnneeScolaire
    annee = AnneeScolaire.objects.filter(active=True).first()
    classes = Classe.objects.filter(annee_scolaire=annee).select_related('section') if annee else []
    paginator = Paginator(ordered_students, PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'students/student_list.html', {
        'students': page_obj,
        'page_obj': page_obj,
        'classes': classes,
        'q': q,
        'classe_id': classe_id,
        'total': paginator.count,
    })


@login_required
@prefet_or_secretariat_required
def student_create(request):
    # Vérification quota avant création
    if request.method == 'POST':
        try:
            from tenants.utils.quotas import get_ecole_from_schema, check_quota
            ecole = get_ecole_from_schema(request.session.get('tenant_schema'))
            ok, msg = check_quota(ecole, 'eleves')
            if not ok:
                messages.error(request, msg)
                return redirect('student_list')
        except Exception:
            pass

    form = StudentForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Élève enregistré avec succès.")
        return redirect('student_list')
    # Tuteur présélectionné depuis l'URL (?tuteur=pk)
    preselected_tuteur = None
    tuteur_pk = request.GET.get('tuteur') or request.POST.get('tuteur')
    if tuteur_pk:
        preselected_tuteur = Tuteur.objects.filter(pk=tuteur_pk).first()
    return render(request, 'students/student_form.html', {
        'form': form,
        'titre': 'Ajouter un élève',
        'preselected_tuteur': preselected_tuteur,
    })


@login_required
@prefet_or_secretariat_required
def student_update(request, pk):
    student = get_object_or_404(Student, pk=pk)
    form = StudentForm(request.POST or None, request.FILES or None, instance=student)
    if form.is_valid():
        form.save()
        messages.success(request, "Élève modifié avec succès.")
        return redirect('student_list')
    return render(request, 'students/student_form.html', {
        'form': form,
        'titre': 'Modifier un élève',
        'obj': student,
        'preselected_tuteur': student.tuteur,
    })


@login_required
@prefet_or_secretariat_required
def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        student.delete()
        messages.success(request, "Élève supprimé.")
        return redirect('student_list')
    return render(request, 'students/student_confirm_delete.html', {'obj': student})


@login_required
def student_detail(request, pk):
    if not request.user.is_prefet_or_secretariat():
        messages.error(request, "Accès non autorisé.")
        return redirect('dashboard')
    student = get_object_or_404(Student.objects.select_related('tuteur', 'classe', 'classe__section'), pk=pk)
    return render(request, 'students/student_detail.html', {'student': student})


# ── Tuteurs ───────────────────────────────────────────────────────────────────

@login_required
@prefet_or_secretariat_required
def tuteur_list(request):
    q = request.GET.get('q', '').strip()
    tuteurs = Tuteur.objects.annotate(nb_enfants=Count('enfants'))
    if q:
        tuteurs = tuteurs.filter(
            Q(nom__icontains=q) | Q(postnom__icontains=q) |
            Q(prenom__icontains=q) | Q(telephone__icontains=q)
        )

    ordered_tuteurs = tuteurs.order_by('nom', 'postnom', 'prenom', 'telephone', 'pk')
    redirect_response = _redirect_to_exact_page(
        request,
        ordered_tuteurs,
        Tuteur.objects.filter(
            Q(nom__iexact=q) | Q(postnom__iexact=q) |
            Q(prenom__iexact=q) | Q(telephone__iexact=q)
        ),
        PER_PAGE,
        'tuteur_list',
    )
    if redirect_response is not None:
        return redirect_response

    paginator = Paginator(ordered_tuteurs, PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'students/tuteur_list.html', {
        'tuteurs': page_obj,
        'page_obj': page_obj,
        'q': q,
        'total': paginator.count,
    })


@login_required
@prefet_or_secretariat_required
def tuteur_create(request):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    form = TuteurForm(request.POST or None)
    if form.is_valid():
        tuteur = form.save()
        messages.success(request, f"Tuteur « {tuteur.nom_complet} » enregistré.")
        if is_ajax:
            return JsonResponse({
                'ok': True,
                'id': tuteur.pk,
                'nom_complet': tuteur.nom_complet,
                'telephone': tuteur.telephone or '',
            })
        next_url = request.GET.get('next') or request.POST.get('next') or ''
        if next_url:
            return redirect(next_url + f'?tuteur={tuteur.pk}')
        return redirect('tuteur_detail', pk=tuteur.pk)
    if is_ajax:
        return JsonResponse({
            'ok': False,
            'errors': {f: [str(e) for e in errs] for f, errs in form.errors.items()},
        }, status=422)
    return render(request, 'students/tuteur_form.html', {
        'form': form,
        'titre': 'Ajouter un tuteur',
    })


@login_required
@prefet_or_secretariat_required
def tuteur_update(request, pk):
    tuteur = get_object_or_404(Tuteur, pk=pk)
    form = TuteurForm(request.POST or None, instance=tuteur)
    if form.is_valid():
        form.save()
        messages.success(request, "Tuteur modifié avec succès.")
        return redirect('tuteur_detail', pk=tuteur.pk)
    return render(request, 'students/tuteur_form.html', {
        'form': form,
        'titre': 'Modifier le tuteur',
        'obj': tuteur,
    })


@login_required
@prefet_or_secretariat_required
def tuteur_detail(request, pk):
    tuteur = get_object_or_404(Tuteur, pk=pk)
    enfants = tuteur.enfants.select_related('classe', 'classe__section').all()
    return render(request, 'students/tuteur_detail.html', {
        'tuteur': tuteur,
        'enfants': enfants,
    })


@login_required
@prefet_or_secretariat_required
def tuteur_delete(request, pk):
    tuteur = get_object_or_404(Tuteur, pk=pk)
    if request.method == 'POST':
        nom = tuteur.nom_complet
        tuteur.delete()
        messages.success(request, f"Tuteur « {nom} » supprimé.")
        return redirect('tuteur_list')
    enfants_count = tuteur.enfants.count()
    return render(request, 'students/tuteur_confirm_delete.html', {
        'obj': tuteur,
        'enfants_count': enfants_count,
    })


@login_required
@prefet_or_secretariat_required
def next_matricule_json(request):
    """Endpoint AJAX — retourne un aperçu du prochain matricule généré."""
    try:
        from school_settings.models import MatriculeConfig
        config = MatriculeConfig.get_config()
        apercu = config.apercu()
        return JsonResponse({'matricule': apercu, 'ok': True})
    except Exception as exc:
        return JsonResponse({'matricule': '', 'ok': False, 'error': str(exc)})


@login_required
@prefet_or_secretariat_required
def tuteur_search_json(request):
    """Endpoint AJAX — retourne les tuteurs correspondant à la recherche."""
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})
    tuteurs = Tuteur.objects.filter(
        Q(nom__icontains=q) | Q(postnom__icontains=q) |
        Q(prenom__icontains=q) | Q(telephone__icontains=q)
    )[:15]
    data = [
        {
            'id': t.pk,
            'text': t.nom_complet,
            'telephone': t.telephone,
        }
        for t in tuteurs
    ]
    return JsonResponse({'results': data})
