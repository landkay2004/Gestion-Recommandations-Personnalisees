from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import render

from .models import Notification


# ─── Page principale ──────────────────────────────────────────────────────────

@login_required
def notification_list(request):
    qs = (
        Notification.objects
        .filter(destinataire=request.user)
        .select_related('expediteur', 'annee_scolaire')
    )

    # ── Filtres ──
    categorie = request.GET.get('categorie', '')
    priorite  = request.GET.get('priorite',  '')
    statut    = request.GET.get('statut',    '')   # 'lue' | 'non_lue' | ''
    q         = request.GET.get('q',         '')

    if categorie:
        qs = qs.filter(categorie=categorie)
    if priorite:
        qs = qs.filter(priorite=priorite)
    if statut == 'lue':
        qs = qs.filter(lue=True)
    elif statut == 'non_lue':
        qs = qs.filter(lue=False)
    if q:
        qs = qs.filter(Q(titre__icontains=q) | Q(description__icontains=q))

    paginator     = Paginator(qs, 25)
    notifications = paginator.get_page(request.GET.get('page', 1))
    nb_non_lues   = Notification.objects.filter(destinataire=request.user, lue=False).count()

    return render(request, 'notifications/list.html', {
        'notifications':     notifications,
        'nb_non_lues':       nb_non_lues,
        'categorie':         categorie,
        'priorite':          priorite,
        'statut':            statut,
        'q':                 q,
        'CATEGORIE_CHOICES': Notification.CATEGORIE_CHOICES,
        'PRIORITE_CHOICES':  Notification.PRIORITE_CHOICES,
    })


# ─── Endpoints AJAX ───────────────────────────────────────────────────────────

@login_required
def notification_count(request):
    """Retourne le nombre de notifications non lues (pour le badge navbar)."""
    count = Notification.objects.filter(destinataire=request.user, lue=False).count()
    return JsonResponse({'count': count})


@login_required
def notification_recentes(request):
    """Retourne les 8 notifications les plus récentes pour le drawer."""
    notifs = (
        Notification.objects
        .filter(destinataire=request.user)
        .select_related('expediteur')
        .order_by('-date_creation')[:8]
    )
    nb_non_lues = Notification.objects.filter(destinataire=request.user, lue=False).count()

    data = [
        {
            'id':          n.pk,
            'titre':       n.titre,
            'description': n.description[:120] + ('…' if len(n.description) > 120 else ''),
            'categorie':   n.get_categorie_display(),
            'priorite':    n.priorite,
            'couleur':     n.couleur,
            'icone':       n.icone,
            'lue':         n.lue,
            'lien':        n.lien,
            'date':        n.date_creation.strftime('%d/%m/%Y'),
            'heure':       n.date_creation.strftime('%H:%M'),
        }
        for n in notifs
    ]
    return JsonResponse({'notifications': data, 'nb_non_lues': nb_non_lues})


# ─── Actions ──────────────────────────────────────────────────────────────────

@login_required
@require_POST
def marquer_lue(request, pk):
    notif = get_object_or_404(Notification, pk=pk, destinataire=request.user)
    notif.lire()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    next_url = notif.lien or 'notification_list'
    return redirect(next_url)


@login_required
@require_POST
def marquer_toutes_lues(request):
    Notification.objects.filter(
        destinataire=request.user, lue=False
    ).update(lue=True, date_lecture=timezone.now())
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    return redirect('notification_list')
