"""
Vues côté école : abonnement, frais scolaires, encaissement comptable.
"""
import logging
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone
from django.template.loader import render_to_string
from django.db.models import Q, Sum
from django.core.paginator import Paginator

from accounts.views import admin_ecole_required, comptable_required

logger = logging.getLogger('sgn')

PER_PAGE = 20


# ════════════════════════════════════════════════════════════════════════════
# ABONNEMENT (vues existantes conservées)
# ════════════════════════════════════════════════════════════════════════════

def ecole_suspendue(request):
    """Page affichée quand l'école est suspendue ou expirée."""
    schema = request.session.get('tenant_schema', '')
    ecole = None
    if schema and schema != 'public':
        try:
            from tenants.models import Ecole
            ecole = Ecole.objects.get(schema_name=schema)
        except Exception:
            pass
    return render(request, 'abonnement/ecole_suspendue.html', {
        'ecole': ecole,
        'ecole_statut': ecole.statut if ecole else '',
        'lecture_seule': ecole.en_grace if ecole else False,
    })


@login_required
def mon_abonnement(request):
    schema = request.session.get('tenant_schema', '')
    ecole = None
    abonnement = None
    quotas = {}
    historique = []

    if schema and schema != 'public':
        try:
            from tenants.models import Ecole, Abonnement
            ecole = Ecole.objects.select_related('plan').get(schema_name=schema)
        except Exception:
            pass

    if ecole:
        try:
            abonnement = ecole.abonnement_detail
            historique = abonnement.historique.select_related(
                'ancien_plan', 'nouveau_plan'
            )[:10]
        except Exception:
            abonnement = None

        try:
            from tenants.utils.quotas import get_quotas_usage
            quotas = get_quotas_usage(ecole)
        except Exception:
            pass

    plans_publics = []
    try:
        from tenants.models import PlanAbonnement
        plans_publics = PlanAbonnement.objects.filter(
            is_actif=True, est_public=True
        ).order_by('ordre_affichage', 'prix_mensuel')
    except Exception:
        pass

    return render(request, 'abonnement/mon_abonnement.html', {
        'ecole':        ecole,
        'abonnement':   abonnement,
        'quotas':       quotas,
        'historique':   historique,
        'plans_publics': plans_publics,
    })


@login_required
def demande_changement(request):
    schema = request.session.get('tenant_schema', '')
    ecole = None
    if schema and schema != 'public':
        try:
            from tenants.models import Ecole
            ecole = Ecole.objects.select_related('plan').get(schema_name=schema)
        except Exception:
            pass

    if not ecole:
        messages.error(request, "Impossible de trouver les informations de votre école.")
        return redirect('abonnement:mon_abonnement')

    from tenants.models import PlanAbonnement
    plans = PlanAbonnement.objects.filter(
        is_actif=True, est_public=True
    ).order_by('ordre_affichage', 'prix_mensuel')

    if request.method == 'POST':
        plan_souhaite_id = request.POST.get('plan_id')
        message_libre = request.POST.get('message', '').strip()

        plan_souhaite = None
        if plan_souhaite_id:
            try:
                plan_souhaite = PlanAbonnement.objects.get(pk=plan_souhaite_id, is_actif=True)
            except PlanAbonnement.DoesNotExist:
                pass

        if not plan_souhaite:
            messages.error(request, "Veuillez sélectionner un plan valide.")
            return render(request, 'abonnement/demande_changement.html', {
                'ecole': ecole, 'plans': plans,
            })

        _envoyer_demande_email(request, ecole, plan_souhaite, message_libre)

        logger.info(
            'DEMANDE_CHANGEMENT_PLAN ecole=%s plan_actuel=%s plan_souhaite=%s',
            ecole.nom,
            ecole.plan.nom if ecole.plan else 'aucun',
            plan_souhaite.nom,
        )

        messages.success(
            request,
            "Votre demande de changement vers le plan « %s » a été envoyée à l'administrateur. "
            "Vous serez contacté dans les plus brefs délais." % plan_souhaite.nom
        )
        return redirect('abonnement:mon_abonnement')

    return render(request, 'abonnement/demande_changement.html', {
        'ecole': ecole,
        'plans': plans,
    })


def _envoyer_demande_email(request, ecole, plan_souhaite, message_libre):
    try:
        from django.core.mail import send_mail
        from django.conf import settings as django_settings

        sujet = "[SGN] Demande de changement de plan — %s" % ecole.nom
        corps = (
            "Demande de changement de plan reçue.\n\n"
            "École           : %s\n"
            "Plan actuel     : %s\n"
            "Plan souhaité   : %s (%.2f USD/mois)\n"
            "Contact         : %s <%s>\n"
        ) % (
            ecole.nom,
            ecole.plan.nom if ecole.plan else 'Aucun',
            plan_souhaite.nom,
            plan_souhaite.prix_mensuel,
            ecole.contact_nom,
            ecole.contact_email,
        )
        if message_libre:
            corps += "\nMessage de l'école :\n%s\n" % message_libre

        send_mail(
            sujet, corps,
            django_settings.DEFAULT_FROM_EMAIL,
            [django_settings.DEFAULT_FROM_EMAIL],
            fail_silently=True,
        )
    except Exception as e:
        logger.warning('DEMANDE_EMAIL_FAILED ecole=%s err=%s', ecole.nom, e)


# ════════════════════════════════════════════════════════════════════════════
# TYPES DE FRAIS (admin_ecole uniquement)
# ════════════════════════════════════════════════════════════════════════════

@login_required
@admin_ecole_required
def frais_list(request):
    from .models import TypeFrais
    frais = TypeFrais.objects.select_related('classe').all()
    return render(request, 'abonnement/frais_list.html', {'frais': frais})


@login_required
@admin_ecole_required
def frais_create(request):
    from .forms import TypeFraisForm
    form = TypeFraisForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Type de frais créé avec succès.")
        return redirect('abonnement:frais_list')
    return render(request, 'abonnement/frais_form.html', {
        'form': form, 'titre': 'Ajouter un type de frais',
    })


@login_required
@admin_ecole_required
def frais_update(request, pk):
    from .models import TypeFrais
    from .forms import TypeFraisForm
    obj = get_object_or_404(TypeFrais, pk=pk)
    form = TypeFraisForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Type de frais modifié.")
        return redirect('abonnement:frais_list')
    return render(request, 'abonnement/frais_form.html', {
        'form': form, 'titre': 'Modifier le type de frais', 'obj': obj,
    })


@login_required
@admin_ecole_required
def frais_delete(request, pk):
    from .models import TypeFrais
    obj = get_object_or_404(TypeFrais, pk=pk)
    if request.method == 'POST':
        # Vérifier qu'aucun paiement n'est lié
        if obj.paiements.exists():
            messages.error(
                request,
                "Impossible de supprimer : des paiements sont liés à ce type de frais. "
                "Désactivez-le à la place."
            )
            return redirect('abonnement:frais_list')
        obj.delete()
        messages.success(request, "Type de frais supprimé.")
        return redirect('abonnement:frais_list')
    return render(request, 'abonnement/frais_confirm_delete.html', {'obj': obj})


# ════════════════════════════════════════════════════════════════════════════
# GESTION DES COMPTABLES (admin_ecole uniquement)
# ════════════════════════════════════════════════════════════════════════════

@login_required
@admin_ecole_required
def comptable_list(request):
    from accounts.models import CustomUser
    comptables = CustomUser.objects.filter(role='comptable').order_by('last_name', 'first_name')
    return render(request, 'abonnement/comptable_list.html', {'comptables': comptables})


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
        return render(request, 'abonnement/comptable_created.html', {
            'new_user': user, 'temp_pwd': temp_pwd,
        })
    return render(request, 'abonnement/comptable_form.html', {
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
        # Synchroniser l'annuaire si l'email a changé
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
        return redirect('abonnement:comptable_list')
    return render(request, 'abonnement/comptable_form.html', {
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
        return render(request, 'abonnement/comptable_reset_confirm.html', {
            'obj': obj, 'temp_pwd': temp_pwd,
        })
    return render(request, 'abonnement/comptable_reset_confirm.html', {'obj': obj})


# ════════════════════════════════════════════════════════════════════════════
# ENCAISSEMENT (comptable)
# ════════════════════════════════════════════════════════════════════════════

@login_required
@comptable_required
def comptable_dashboard(request):
    from .models import Paiement, Facture
    from accounts.models import CustomUser

    # Statistiques rapides
    total_paiements = Paiement.objects.count()
    paiements_du_jour = Paiement.objects.filter(
        date_paiement__date=timezone.now().date()
    ).count()
    montant_du_jour = Paiement.objects.filter(
        date_paiement__date=timezone.now().date()
    ).aggregate(s=Sum('montant_paye'))['s'] or Decimal('0')

    derniers = Paiement.objects.select_related(
        'eleve', 'type_frais', 'facture'
    ).order_by('-date_paiement')[:10]

    return render(request, 'abonnement/comptable_dashboard.html', {
        'total_paiements': total_paiements,
        'paiements_du_jour': paiements_du_jour,
        'montant_du_jour': montant_du_jour,
        'derniers': derniers,
    })


@login_required
@comptable_required
def recherche_eleve(request):
    """Recherche d'un élève par nom ou matricule avant encaissement."""
    from students.models import Student
    q = request.GET.get('q', '').strip()
    eleves = []
    if q:
        eleves = Student.objects.select_related('classe').filter(
            Q(nom__icontains=q) |
            Q(postnom__icontains=q) |
            Q(prenom__icontains=q) |
            Q(matricule__icontains=q)
        ).order_by('nom', 'postnom')[:30]

    return render(request, 'abonnement/recherche_eleve.html', {
        'q': q, 'eleves': eleves,
    })


@login_required
@comptable_required
def encaissement(request, eleve_pk):
    """Formulaire d'encaissement pour un élève."""
    from students.models import Student
    from .models import Paiement, Facture
    from .forms import PaiementForm
    from .utils import get_frais_a_payer

    eleve = get_object_or_404(Student, pk=eleve_pk)
    frais_a_payer = get_frais_a_payer(eleve)

    if not frais_a_payer:
        messages.info(request, "Cet élève n'a aucun frais impayé.")
        return redirect('abonnement:recherche_eleve')

    form = PaiementForm(request.POST or None, eleve=eleve)

    if request.method == 'POST' and form.is_valid():
        # Vérification finale côté serveur
        type_frais = form.cleaned_data['type_frais']
        montant = form.cleaned_data['montant_paye']

        frais_restants = get_frais_a_payer(eleve)
        frais_valide = next(
            (f for f in frais_restants if f['type_frais'].pk == type_frais.pk),
            None
        )
        if not frais_valide:
            messages.error(request, "Ce frais est déjà soldé ou invalide.")
            return redirect('abonnement:encaissement', eleve_pk=eleve.pk)
        if montant > frais_valide['reste_du']:
            messages.error(
                request,
                f"Montant ({montant}) supérieur au reste dû ({frais_valide['reste_du']})."
            )
            return redirect('abonnement:encaissement', eleve_pk=eleve.pk)

        paiement = form.save(commit=False)
        paiement.eleve = eleve
        paiement.comptable = request.user
        paiement.save()

        # Générer la facture automatiquement
        numero = Facture.generer_numero()
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
        return redirect('abonnement:facture_detail', pk=facture.pk)

    return render(request, 'abonnement/encaissement.html', {
        'eleve': eleve,
        'form': form,
        'frais_a_payer': frais_a_payer,
    })


# ════════════════════════════════════════════════════════════════════════════
# HISTORIQUE & FACTURES
# ════════════════════════════════════════════════════════════════════════════

@login_required
@comptable_required
def historique_paiements(request):
    from .models import Paiement
    from students.models import Student
    from accounts.models import CustomUser

    qs = Paiement.objects.select_related(
        'eleve', 'eleve__classe', 'type_frais', 'facture', 'comptable'
    )

    # Filtres
    q_eleve = request.GET.get('eleve', '').strip()
    q_frais = request.GET.get('frais', '').strip()
    q_comptable = request.GET.get('comptable', '').strip()
    date_debut = request.GET.get('date_debut', '').strip()
    date_fin = request.GET.get('date_fin', '').strip()

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
            d = date.fromisoformat(date_debut)
            qs = qs.filter(date_paiement__date__gte=d)
        except ValueError:
            pass
    if date_fin:
        try:
            from datetime import date
            d = date.fromisoformat(date_fin)
            qs = qs.filter(date_paiement__date__lte=d)
        except ValueError:
            pass

    total_filtre = qs.aggregate(s=Sum('montant_paye'))['s'] or Decimal('0')
    paginator = Paginator(qs.order_by('-date_paiement'), PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Listes pour les filtres select
    comptables = CustomUser.objects.filter(role='comptable').order_by('last_name')

    return render(request, 'abonnement/historique_paiements.html', {
        'page_obj': page_obj,
        'total_filtre': total_filtre,
        'q_eleve': q_eleve,
        'q_frais': q_frais,
        'q_comptable': q_comptable,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'comptables': comptables,
    })


@login_required
@comptable_required
def facture_detail(request, pk):
    from .models import Facture
    from .utils import get_frais_a_payer

    facture = get_object_or_404(
        Facture.objects.select_related(
            'paiement', 'paiement__eleve', 'paiement__eleve__classe',
            'paiement__type_frais', 'paiement__comptable',
        ),
        pk=pk,
    )
    paiement = facture.paiement
    eleve = paiement.eleve
    type_frais = paiement.type_frais

    # Recalculer reste dû après ce paiement
    from django.db.models import Sum as DSum
    total_paye_all = (
        eleve.paiements.filter(type_frais=type_frais)
        .aggregate(s=DSum('montant_paye'))['s']
    ) or Decimal('0')
    reste_du = max(type_frais.montant - total_paye_all, Decimal('0'))

    # Logo de l'école depuis le schéma public
    ecole = None
    try:
        from tenants.models import Ecole
        schema = request.session.get('tenant_schema', '')
        if schema:
            ecole = Ecole.objects.get(schema_name=schema)
    except Exception:
        pass

    return render(request, 'abonnement/facture_detail.html', {
        'facture': facture,
        'paiement': paiement,
        'eleve': eleve,
        'type_frais': type_frais,
        'reste_du': reste_du,
        'ecole': ecole,
    })


@login_required
@comptable_required
def facture_pdf(request, pk):
    """Génère un PDF de la facture via ReportLab."""
    from .models import Facture
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
    paiement = facture.paiement
    eleve = paiement.eleve
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

    styles = getSampleStyleSheet()
    title_style  = ParagraphStyle('Title',  parent=styles['Normal'], fontSize=16, fontName='Helvetica-Bold',  alignment=TA_CENTER, spaceAfter=4)
    school_style = ParagraphStyle('School', parent=styles['Normal'], fontSize=11, fontName='Helvetica-Bold',  alignment=TA_CENTER, spaceAfter=2)
    center_style = ParagraphStyle('Center', parent=styles['Normal'], fontSize=9,  fontName='Helvetica',       alignment=TA_CENTER)
    label_style  = ParagraphStyle('Label',  parent=styles['Normal'], fontSize=9,  fontName='Helvetica-Bold')
    value_style  = ParagraphStyle('Value',  parent=styles['Normal'], fontSize=9,  fontName='Helvetica')
    total_style  = ParagraphStyle('Total',  parent=styles['Normal'], fontSize=11, fontName='Helvetica-Bold',  alignment=TA_RIGHT)

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

    # Infos élève
    eleve_data = [
        ['Élève', eleve.nom_complet],
        ['Matricule', eleve.matricule],
        ['Classe', str(eleve.classe) if eleve.classe else '—'],
        ['Date', facture.date_emission.strftime('%d/%m/%Y %H:%M')],
        ['Comptable', paiement.comptable.get_full_name() or paiement.comptable.username],
    ]
    t_info = Table(eleve_data, colWidths=[4*cm, 12*cm])
    t_info.setStyle(TableStyle([
        ('FONTNAME',    (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME',    (1,0), (1,-1), 'Helvetica'),
        ('FONTSIZE',    (0,0), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('GRID',        (0,0), (-1,-1), 0.3, colors.lightgrey),
        ('BACKGROUND',  (0,0), (0,-1), LIGHT),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 0.5*cm))

    # Détail frais
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
        ('BACKGROUND',  (0,0), (-1,0), PURPLE),
        ('TEXTCOLOR',   (0,0), (-1,0), colors.white),
        ('FONTNAME',    (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME',    (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE',    (0,0), (-1,-1), 9),
        ('ALIGN',       (1,0), (-1,-1), 'CENTER'),
        ('GRID',        (0,0), (-1,-1), 0.3, colors.lightgrey),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT]),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
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
