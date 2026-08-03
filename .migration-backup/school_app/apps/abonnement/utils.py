"""
Utilitaires pour la gestion des frais scolaires.
"""
from decimal import Decimal
from django.db.models import Sum


def get_frais_a_payer(eleve):
    """
    Retourne la liste des TypeFrais applicables à l'élève avec montant payé
    et reste dû, en excluant les frais entièrement soldés.

    Optimisé : une seule requête pour tous les totaux payés via annotation
    (évite N queries pour N types de frais).

    Format de retour :
        [
            {
                'type_frais': TypeFrais,
                'montant_total': Decimal,
                'montant_paye': Decimal,
                'reste_du': Decimal,
            },
            ...
        ]
    """
    from .models import TypeFrais, Paiement
    from django.db.models import Q, OuterRef, Subquery, DecimalField, Value
    from django.db.models.functions import Coalesce

    # TypeFrais actifs applicables à cet élève :
    # (classe nulle = tous les élèves) OU (classe == élève.classe)
    types = TypeFrais.objects.filter(actif=True).filter(
        Q(classe__isnull=True) | Q(classe=eleve.classe)
    ).select_related('classe')

    # Totaux payés par type de frais — une seule requête via dict
    totaux = (
        Paiement.objects
        .filter(eleve=eleve, type_frais__in=types)
        .values('type_frais_id')
        .annotate(total=Sum('montant_paye'))
    )
    totaux_map = {row['type_frais_id']: row['total'] for row in totaux}

    result = []
    for tf in types:
        total_paye = totaux_map.get(tf.pk) or Decimal('0')
        reste = max(tf.montant - total_paye, Decimal('0'))
        if reste > Decimal('0'):
            result.append({
                'type_frais': tf,
                'montant_total': tf.montant,
                'montant_paye': total_paye,
                'reste_du': reste,
            })

    return result


def get_historique_paiements(eleve, limit=None):
    """
    Retourne l'historique complet des paiements d'un élève,
    avec select_related pour éviter les N+1.
    """
    from .models import Paiement
    qs = (
        Paiement.objects
        .filter(eleve=eleve)
        .select_related('type_frais', 'facture', 'comptable')
        .order_by('-date_paiement')
    )
    if limit:
        qs = qs[:limit]
    return list(qs)


def get_resume_frais(eleve):
    """
    Retourne un résumé des frais (tous frais, payés ou non) avec statut.
    Utilisé pour afficher l'état complet d'un élève.
    """
    from .models import TypeFrais, Paiement
    from django.db.models import Q

    types = TypeFrais.objects.filter(actif=True).filter(
        Q(classe__isnull=True) | Q(classe=eleve.classe)
    ).select_related('classe')

    totaux = (
        Paiement.objects
        .filter(eleve=eleve, type_frais__in=types)
        .values('type_frais_id')
        .annotate(total=Sum('montant_paye'))
    )
    totaux_map = {row['type_frais_id']: row['total'] for row in totaux}

    result = []
    for tf in types:
        total_paye = totaux_map.get(tf.pk) or Decimal('0')
        reste = max(tf.montant - total_paye, Decimal('0'))
        result.append({
            'type_frais': tf,
            'montant_total': tf.montant,
            'montant_paye': total_paye,
            'reste_du': reste,
            'solde': reste == Decimal('0'),
        })
    return result
