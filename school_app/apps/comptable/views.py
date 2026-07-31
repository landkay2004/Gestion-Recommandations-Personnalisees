"""
Vues du module comptable :
  - Gestion des comptes comptable (admin_ecole)
  - Espace caisse : recherche élève, encaissement, historique, factures PDF
"""
import logging
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q, Sum
from django.core.paginator import Paginator

from accounts.views import admin_ecole_required, comptable_required
from abonnement.models import Paiement, Facture, TypeFrais

logger = logging.getLogger('sgn')
PER_PAGE = 20


# ════════════════════════════════════════════════════════════════════════════
# GESTION DES COMPTABLES (admin_ecole)
# ════════════════════════════════════════════════════════════════════════════

@login_required
@admin_ecole_required
def comptable_list(request):
    from accounts.models import CustomUser
    comptables = CustomUser.objects.filter(role='comptable').order_by('last_name', 'first_name')
    return render(request, 'comptable/comptable_list.html', {'comptables': comptables})


@login_required
@admin_ecole_required
def comptable_create(request):
    from .forms import ComptableCreateForm
    form = ComptableCreateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        schema = request.session.get('tenant_schema', 'public')
        user, temp_pwd = form.save(schema_name=schema)
        messages.success(
            request,
            f"Compte comptable créé. Mot de passe temporaire : {temp_pwd}"
        )
        return render(request, 'comptable/comptable_created.html', {
            'new_user': user, 'temp_pwd': temp_pwd,
        })
    return render(request, 'comptable/comptable_form.html', {
        'form': form, 'titre': 'Ajouter un comptable',
    })


@login_required
@admin_ecole_required
def comptable_update(request, pk):
    from accounts.models import CustomUser
    from .forms import ComptableUpdateForm
    obj = get_object_or_404(CustomUser, pk=pk, role='comptable')
    old_email = obj.email.lower()
    form = ComptableUpdateForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        updated = form.save()
        try:
            from tenants.models import AnnuaireUtilisateur
            new_email = updated.email.lower()
            schema = request.session.get('tenant_schema', 'public')
            if old_email != new_email:
                AnnuaireUtilisateur.objects.filter(email=old_email).delete()
                AnnuaireUtilisateur.objects.get_or_create(
                    email=new_email,
                    defaults={'schema_name': schema, 'type_compte': 'comptable'},
                )
        except Exception:
            pass
        messages.success(request, "Compte comptable mis à jour.")
        return redirect('comptable:comptable_list')
    return render(request, 'comptable/comptable_form.html', {
        'form': form, 'titre': 'Modifier le comptable', 'obj': obj,
    })


@login_required
@admin_ecole_required
def comptable_reset_password(request, pk):
    from accounts.models import CustomUser, generate_temp_password
    obj = get_object_or_404(CustomUser, pk=pk, role='comptable')
    if request.method == 'POST':
        temp_pwd = generate_temp_password()
        obj.set_password(temp_pwd)
        obj.must_change_password = True
        obj.save(update_fields=['password', 'must_change_password'])
        messages.success(request, f"Mot de passe réinitialisé : {temp_pwd}")
        return render(request, 'comptable/comptable_reset_confirm.html', {
            'obj': obj, 'temp_pwd': temp_pwd,
        })
    return render(request, 'comptable/comptable_reset_confirm.html', {'obj': obj})


# ════════════════════════════════════════════════════════════════════════════
# ESPACE CAISSE (comptable)
# ════════════════════════════════════════════════════════════════════════════

@login_required
@comptable_required
def comptable_dashboard(request):
    from accounts.models import CustomUser

    total_paiements   = Paiement.objects.count()
    paiements_du_jour = Paiement.objects.filter(
        date_paiement__date=timezone.now().date()
    ).count()
    montant_du_jour   = Paiement.objects.filter(
        date_paiement__date=timezone.now().date()
    ).aggregate(s=Sum('montant_paye'))['s'] or Decimal('0')

    derniers = Paiement.objects.select_related(
        'eleve', 'type_frais', 'facture'
    ).order_by('-date_paiement')[:10]

    return render(request, 'comptable/dashboard.html', {
        'total_paiements':   total_paiements,
        'paiements_du_jour': paiements_du_jour,
        'montant_du_jour':   montant_du_jour,
        'derniers':          derniers,
    })


@login_required
@comptable_required
def recherche_eleve(request):
    """Recherche d'un élève avant encaissement (supporte AJAX pour résultats dynamiques)."""
    from students.models import Student
    import json

    q = request.GET.get('q', '').strip()
    eleves = []
    if q and len(q) >= 2:
        eleves = Student.objects.select_related('classe').filter(
            Q(nom__icontains=q) |
            Q(postnom__icontains=q) |
            Q(prenom__icontains=q) |
            Q(matricule__icontains=q)
        ).order_by('nom', 'postnom')[:30]

    # Réponse JSON pour les requêtes AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.urls import reverse
        data = [
            {
                'pk':        e.pk,
                'nom':       e.nom_complet,
                'matricule': e.matricule,
                'classe':    str(e.classe) if e.classe else '',
                'url':       reverse('comptable:encaissement', args=[e.pk]),
            }
            for e in eleves
        ]
        return HttpResponse(
            json.dumps({'results': data, 'count': len(data)}),
            content_type='application/json',
        )

    return render(request, 'comptable/recherche_eleve.html', {
        'q': q, 'eleves': eleves,
    })


@login_required
@comptable_required
def encaissement(request, eleve_pk):
    """Formulaire d'encaissement pour un élève — affiche toujours l'historique."""
    from students.models import Student
    from abonnement.utils import get_frais_a_payer, get_historique_paiements, get_resume_frais
    from .forms import PaiementForm

    eleve         = get_object_or_404(Student.objects.select_related('classe'), pk=eleve_pk)
    frais_a_payer = get_frais_a_payer(eleve)
    historique    = get_historique_paiements(eleve)
    resume_frais  = get_resume_frais(eleve)

    # Total général payé pour cet élève
    total_paye = sum(p.montant_paye for p in historique)

    form = PaiementForm(request.POST or None, eleve=eleve) if frais_a_payer else None

    if request.method == 'POST':
        if not frais_a_payer:
            messages.warning(request, "Cet élève n'a aucun frais impayé à encaisser.")
        elif form and form.is_valid():
            type_frais = form.cleaned_data['type_frais']
            montant    = form.cleaned_data['montant_paye']

            frais_restants = get_frais_a_payer(eleve)
            frais_valide   = next(
                (f for f in frais_restants if f['type_frais'].pk == type_frais.pk),
                None
            )
            if not frais_valide:
                messages.error(request, "Ce frais est déjà soldé ou invalide.")
            elif montant > frais_valide['reste_du']:
                messages.error(
                    request,
                    f"Montant ({montant}) supérieur au reste dû ({frais_valide['reste_du']})."
                )
            else:
                paiement           = form.save(commit=False)
                paiement.eleve     = eleve
                paiement.comptable = request.user
                paiement.save()

                numero  = Facture.generer_numero()
                facture = Facture.objects.create(paiement=paiement, numero_facture=numero)

                logger.info(
                    'PAIEMENT_ENREGISTRE ref=%s eleve=%s frais=%s montant=%s comptable=%s',
                    paiement.reference, eleve.nom_complet, type_frais.nom,
                    montant, request.user.username,
                )

                messages.success(
                    request,
                    f"Paiement enregistré. Facture n° {facture.numero_facture} générée."
                )
                return redirect('comptable:facture_detail', pk=facture.pk)

    return render(request, 'comptable/encaissement.html', {
        'eleve':        eleve,
        'form':         form,
        'frais_a_payer': frais_a_payer,
        'historique':   historique,
        'resume_frais': resume_frais,
        'total_paye':   total_paye,
    })


@login_required
@comptable_required
def historique_paiements(request):
    from accounts.models import CustomUser

    qs = Paiement.objects.select_related(
        'eleve', 'eleve__classe', 'type_frais', 'facture', 'comptable'
    )

    q_eleve     = request.GET.get('eleve', '').strip()
    q_frais     = request.GET.get('frais', '').strip()
    q_comptable = request.GET.get('comptable', '').strip()
    date_debut  = request.GET.get('date_debut', '').strip()
    date_fin    = request.GET.get('date_fin', '').strip()

    if q_eleve:
        qs = qs.filter(
            Q(eleve__nom__icontains=q_eleve) |
            Q(eleve__postnom__icontains=q_eleve) |
            Q(eleve__matricule__icontains=q_eleve)
        )
    if q_frais:
        qs = qs.filter(type_frais__nom__icontains=q_frais)
    if q_comptable:
        qs = qs.filter(
            Q(comptable__first_name__icontains=q_comptable) |
            Q(comptable__last_name__icontains=q_comptable)
        )
    if date_debut:
        try:
            from datetime import date
            qs = qs.filter(date_paiement__date__gte=date.fromisoformat(date_debut))
        except ValueError:
            pass
    if date_fin:
        try:
            from datetime import date
            qs = qs.filter(date_paiement__date__lte=date.fromisoformat(date_fin))
        except ValueError:
            pass

    total_filtre = qs.aggregate(s=Sum('montant_paye'))['s'] or Decimal('0')
    paginator    = Paginator(qs.order_by('-date_paiement'), PER_PAGE)
    page_obj     = paginator.get_page(request.GET.get('page'))
    comptables   = CustomUser.objects.filter(role='comptable').order_by('last_name')

    return render(request, 'comptable/historique_paiements.html', {
        'page_obj':    page_obj,
        'total_filtre': total_filtre,
        'q_eleve':     q_eleve,
        'q_frais':     q_frais,
        'q_comptable': q_comptable,
        'date_debut':  date_debut,
        'date_fin':    date_fin,
        'comptables':  comptables,
    })


@login_required
@comptable_required
def facture_detail(request, pk):
    from django.db.models import Sum as DSum

    facture = get_object_or_404(
        Facture.objects.select_related(
            'paiement', 'paiement__eleve', 'paiement__eleve__classe',
            'paiement__type_frais', 'paiement__comptable',
        ),
        pk=pk,
    )
    paiement   = facture.paiement
    eleve      = paiement.eleve
    type_frais = paiement.type_frais

    total_paye_all = (
        eleve.paiements.filter(type_frais=type_frais)
        .aggregate(s=DSum('montant_paye'))['s']
    ) or Decimal('0')
    reste_du = max(type_frais.montant - total_paye_all, Decimal('0'))

    ecole = None
    try:
        from tenants.models import Ecole
        schema = request.session.get('tenant_schema', '')
        if schema:
            ecole = Ecole.objects.get(schema_name=schema)
    except Exception:
        pass

    return render(request, 'comptable/facture_detail.html', {
        'facture':    facture,
        'paiement':   paiement,
        'eleve':      eleve,
        'type_frais': type_frais,
        'reste_du':   reste_du,
        'ecole':      ecole,
    })


@login_required
@comptable_required
def facture_pdf(request, pk):
    """Génère un PDF de la facture via ReportLab."""
    from django.db.models import Sum as DSum
    import io

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    except ImportError:
        return HttpResponse("ReportLab non disponible.", status=500)

    facture = get_object_or_404(
        Facture.objects.select_related(
            'paiement', 'paiement__eleve', 'paiement__eleve__classe',
            'paiement__type_frais', 'paiement__comptable',
        ),
        pk=pk,
    )
    paiement   = facture.paiement
    eleve      = paiement.eleve
    type_frais = paiement.type_frais

    total_paye_all = (
        eleve.paiements.filter(type_frais=type_frais)
        .aggregate(s=DSum('montant_paye'))['s']
    ) or Decimal('0')
    reste_du = max(type_frais.montant - total_paye_all, Decimal('0'))

    ecole_nom = "École"
    try:
        from tenants.models import Ecole
        schema = request.session.get('tenant_schema', '')
        if schema:
            ec = Ecole.objects.get(schema_name=schema)
            ecole_nom = ec.nom
    except Exception:
        pass

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        leftMargin=2*cm, rightMargin=2*cm,
    )

    styles      = getSampleStyleSheet()
    title_style  = ParagraphStyle('Title',  parent=styles['Normal'], fontSize=16, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=4)
    school_style = ParagraphStyle('School', parent=styles['Normal'], fontSize=11, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=2)
    center_style = ParagraphStyle('Center', parent=styles['Normal'], fontSize=9,  fontName='Helvetica',      alignment=TA_CENTER)
    value_style  = ParagraphStyle('Value',  parent=styles['Normal'], fontSize=9,  fontName='Helvetica')

    PURPLE = colors.HexColor('#4D44B5')
    LIGHT  = colors.HexColor('#F0EFFC')

    story = []
    story.append(Paragraph(ecole_nom, school_style))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width='100%', thickness=2, color=PURPLE))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph('REÇU DE PAIEMENT', title_style))
    story.append(Paragraph(f'N° {facture.numero_facture}', center_style))
    story.append(Spacer(1, 0.5*cm))

    eleve_data = [
        ['Élève',     eleve.nom_complet],
        ['Matricule', eleve.matricule],
        ['Classe',    str(eleve.classe) if eleve.classe else '—'],
        ['Date',      facture.date_emission.strftime('%d/%m/%Y %H:%M')],
        ['Comptable', paiement.comptable.get_full_name() or paiement.comptable.username],
    ]
    t_info = Table(eleve_data, colWidths=[4*cm, 12*cm])
    t_info.setStyle(TableStyle([
        ('FONTNAME',      (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME',      (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID',          (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ('BACKGROUND',    (0, 0), (0, -1), LIGHT),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 0.5*cm))

    frais_data = [
        ['Désignation', 'Montant total', 'Payé ce jour', 'Total payé', 'Reste dû'],
        [
            type_frais.nom,
            f"{type_frais.montant:.2f} USD",
            f"{paiement.montant_paye:.2f} USD",
            f"{total_paye_all:.2f} USD",
            f"{reste_du:.2f} USD",
        ],
    ]
    t_frais = Table(frais_data, colWidths=[6*cm, 3*cm, 3*cm, 3*cm, 3*cm])
    t_frais.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), PURPLE),
        ('TEXTCOLOR',     (0, 0), (-1, 0), colors.white),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 0), (-1, -1), 9),
        ('ALIGN',         (1, 0), (-1, -1), 'CENTER'),
        ('GRID',          (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, LIGHT]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_frais)
    story.append(Spacer(1, 0.3*cm))

    mode_label = dict(paiement.MODE_CHOICES).get(paiement.mode_paiement, paiement.mode_paiement)
    story.append(Paragraph(f'Mode de paiement : {mode_label}', value_style))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(f'Référence : {paiement.reference}', center_style))
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width='100%', thickness=1, color=colors.lightgrey))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph('Ce document tient lieu de reçu officiel.', center_style))

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'inline; filename="facture_{facture.numero_facture}.pdf"'
    )
    return response
