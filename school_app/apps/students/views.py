from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Student
from .forms import StudentForm
from accounts.views import prefet_required

PER_PAGE = 20


@login_required
@prefet_required
def student_list(request):
    q = request.GET.get('q', '')
    classe_id = request.GET.get('classe', '')
    students = Student.objects.select_related('classe', 'classe__section')
    if q:
        students = students.filter(
            Q(nom__icontains=q) | Q(postnom__icontains=q) |
            Q(prenom__icontains=q) | Q(matricule__icontains=q)
        )
    if classe_id:
        students = students.filter(classe_id=classe_id)
    from classes.models import Classe, AnneeScolaire
    annee = AnneeScolaire.objects.filter(active=True).first()
    classes = Classe.objects.filter(annee_scolaire=annee).select_related('section') if annee else []
    paginator = Paginator(students, PER_PAGE)
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
@prefet_required
def student_create(request):
    form = StudentForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Élève enregistré avec succès.")
        return redirect('student_list')
    return render(request, 'students/student_form.html', {'form': form, 'titre': 'Ajouter un élève'})


@login_required
@prefet_required
def student_update(request, pk):
    student = get_object_or_404(Student, pk=pk)
    form = StudentForm(request.POST or None, request.FILES or None, instance=student)
    if form.is_valid():
        form.save()
        messages.success(request, "Élève modifié avec succès.")
        return redirect('student_list')
    return render(request, 'students/student_form.html', {'form': form, 'titre': 'Modifier un élève', 'obj': student})


@login_required
@prefet_required
def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        student.delete()
        messages.success(request, "Élève supprimé.")
        return redirect('student_list')
    return render(request, 'students/student_confirm_delete.html', {'obj': student})


@login_required
def student_detail(request, pk):
    student = get_object_or_404(Student, pk=pk)
    return render(request, 'students/student_detail.html', {'student': student})
