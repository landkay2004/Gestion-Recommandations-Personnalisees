from urllib.parse import urlencode
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse
from .models import Teacher
from .forms import TeacherForm
from accounts.views import prefet_required, prefet_or_secretariat_required

PER_PAGE = 15


def _redirect_to_exact_page(request, ordered_qs, exact_qs, page_size, url_name):
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
    return redirect(f"{reverse(url_name)}?{urlencode(params)}")


@login_required
@prefet_or_secretariat_required
def teacher_list(request):
    q = request.GET.get('q', '').strip()
    teachers = Teacher.objects.select_related('user')
    if q:
        teachers = teachers.filter(
            Q(user__first_name__icontains=q) |
            Q(postnom__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(user__email__icontains=q)
        )

    ordered_teachers = teachers.order_by('user__last_name', 'user__first_name', 'postnom', 'user__email', 'pk')
    redirect_response = _redirect_to_exact_page(
        request,
        ordered_teachers,
        Teacher.objects.select_related('user').filter(
            Q(user__first_name__iexact=q) |
            Q(postnom__iexact=q) |
            Q(user__last_name__iexact=q) |
            Q(user__email__iexact=q)
        ),
        PER_PAGE,
        'teacher_list',
    )
    if redirect_response is not None:
        return redirect_response

    paginator = Paginator(ordered_teachers, PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'teachers/teacher_list.html', {
        'teachers': page_obj,
        'page_obj': page_obj,
        'q': q,
        'total': paginator.count,
    })


@login_required
@prefet_or_secretariat_required
def teacher_create(request):
    # Vérification quota avant création
    if request.method == 'POST':
        try:
            from tenants.utils.quotas import get_ecole_from_schema, check_quota
            ecole = get_ecole_from_schema(request.session.get('tenant_schema'))
            ok, msg = check_quota(ecole, 'enseignants')
            if not ok:
                messages.error(request, msg)
                return redirect('teacher_list')
        except Exception:
            pass

    form = TeacherForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        teacher, temp_password = form.save()
        return render(request, 'teachers/teacher_created.html', {
            'teacher': teacher,
            'temp_password': temp_password,
        })
    return render(request, 'teachers/teacher_form.html', {'form': form, 'titre': 'Ajouter un enseignant'})


@login_required
@prefet_or_secretariat_required
def teacher_update(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    form = TeacherForm(request.POST or None, request.FILES or None, instance=teacher)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Enseignant modifié avec succès.")
        return redirect('teacher_list')
    return render(request, 'teachers/teacher_form.html', {'form': form, 'titre': 'Modifier un enseignant', 'obj': teacher})


@login_required
@prefet_or_secretariat_required
def teacher_delete(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    if request.method == 'POST':
        teacher.user.delete()
        messages.success(request, "Enseignant supprimé.")
        return redirect('teacher_list')
    return render(request, 'teachers/teacher_confirm_delete.html', {'obj': teacher})


@login_required
def teacher_detail(request, pk):
    if not request.user.is_prefet_or_secretariat():
        messages.error(request, "Accès non autorisé.")
        return redirect('dashboard')
    teacher = get_object_or_404(Teacher, pk=pk)
    return render(request, 'teachers/teacher_detail.html', {'teacher': teacher})
