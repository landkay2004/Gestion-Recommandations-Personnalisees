"""
Utilitaires pour la gestion des frais scolaires.
"""
from decimal import Decimal
from django.db.models import Sum


def get_frais_a_payer(eleve):
    """
    Retourne la liste des TypeFrais applicables à l'élève avec montant payé
    et reste dû, en excluant les frais entièrement soldés.

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

    # TypeFrais actifs applicables à cet élève :
    # (classe nulle = tous les élèves) OU (classe == élève.classe)
    from django.db.models import Q
    types = TypeFrais.objects.filter(actif=True).filter(
        Q(classe__isnull=True) | Q(classe=eleve.classe)
    )

    result = []
    for tf in types:
        total_paye = (
            Paiement.objects.filter(eleve=eleve, type_frais=tf)
            .aggregate(s=Sum('montant_paye'))['s']
        ) or Decimal('0')

        reste = max(tf.montant - total_paye, Decimal('0'))
        if reste > Decimal('0'):
            result.append({
                'type_frais': tf,
                'montant_total': tf.montant,
                'montant_paye': total_paye,
                'reste_du': reste,
            })

    return result
