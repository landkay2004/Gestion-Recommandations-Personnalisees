"""
Utilitaires de vérification de quotas (plan d'abonnement).
Utilisés depuis les vues de création d'élèves, enseignants, classes et utilisateurs.
"""
from tenants.models import MODULES_SGN, FONCTIONNALITES_SGN, MODULES_DICT, FONCTIONNALITES_DICT

# Mapping URL préfixe → clé module
MODULE_URL_MAP = {
    '/notes/':        'notes',
    '/bulletins/':    'bulletins',
    '/classes/':      'classes',
    '/eleves/':       'eleves',
    '/enseignants/':  'enseignants',
    '/planning/':     'planning',
    '/portail/':      'portail_parents',
    '/cartes/':       'carte_eleve',
    '/rapports/':     'rapports',
    '/notifications/': 'notifications',
}


def get_ecole_from_schema(schema_name):
    """Retourne l'Ecole correspondant au schema_name, ou None."""
    if not schema_name or schema_name == 'public':
        return None
    try:
        from tenants.models import Ecole
        return Ecole.objects.select_related('plan').get(schema_name=schema_name)
    except Exception:
        return None


def check_quota(ecole, resource_type):
    """
    Vérifie si la création d'une nouvelle ressource est autorisée par le plan.

    Args:
        ecole: instance Ecole (plan chargé via select_related recommandé)
        resource_type: 'eleves' | 'enseignants' | 'classes' | 'utilisateurs'

    Returns:
        (ok: bool, message: str)
    """
    if not ecole or not ecole.plan:
        return True, ''

    plan = ecole.plan

    try:
        if resource_type == 'eleves':
            limit = plan.max_eleves
            from students.models import Student
            count = Student.objects.count()
        elif resource_type == 'enseignants':
            limit = plan.max_enseignants
            from teachers.models import Teacher
            count = Teacher.objects.count()
        elif resource_type == 'classes':
            limit = plan.max_classes
            from classes.models import Classe, AnneeScolaire
            annee = AnneeScolaire.objects.filter(active=True).first()
            count = Classe.objects.filter(annee_scolaire=annee).count() if annee else 0
        elif resource_type == 'utilisateurs':
            limit = plan.max_utilisateurs
            from accounts.models import CustomUser
            count = CustomUser.objects.filter(is_active=True).count()
        else:
            return True, ''

        if limit > 0 and count >= limit:
            labels = {
                'eleves':        'élèves',
                'enseignants':   'enseignants',
                'classes':       'classes',
                'utilisateurs':  'utilisateurs',
            }
            label = labels.get(resource_type, resource_type)
            return False, (
                "Quota %s atteint (%d/%d — plan « %s »). "
                "Contactez l'administrateur pour mettre à niveau votre abonnement."
                % (label, count, limit, plan.nom)
            )
    except Exception:
        pass  # En cas d'erreur technique, on laisse passer

    return True, ''


def check_module_access(ecole, module_key):
    """
    Vérifie si le module est autorisé par le plan de l'école.
    Retourne True si le plan n'a pas de liste de modules (rétrocompatibilité).
    """
    if not ecole or not ecole.plan:
        return True
    modules = ecole.plan.modules_inclus or []
    if not modules:
        return True  # liste vide = tous les modules autorisés
    return module_key in modules


def get_quotas_usage(ecole):
    """
    Retourne l'utilisation actuelle des quotas pour l'école (déjà dans le bon schema).
    À appeler uniquement depuis une vue tenant (schema déjà basculé sur l'école).

    Returns: dict avec clés eleves/enseignants/classes/utilisateurs →
             {count, limit, pct, alerte}
    """
    if not ecole or not ecole.plan:
        return {}

    plan = ecole.plan
    result = {}

    def _entry(count, limit):
        pct = round(count / limit * 100) if limit > 0 else 0
        return {'count': count, 'limit': limit, 'pct': pct, 'alerte': pct >= 80}

    try:
        from students.models import Student
        result['eleves'] = _entry(Student.objects.count(), plan.max_eleves)
    except Exception:
        result['eleves'] = _entry(0, plan.max_eleves)

    try:
        from teachers.models import Teacher
        result['enseignants'] = _entry(Teacher.objects.count(), plan.max_enseignants)
    except Exception:
        result['enseignants'] = _entry(0, plan.max_enseignants)

    try:
        from classes.models import Classe, AnneeScolaire
        annee = AnneeScolaire.objects.filter(active=True).first()
        count = Classe.objects.filter(annee_scolaire=annee).count() if annee else 0
        result['classes'] = _entry(count, plan.max_classes)
    except Exception:
        result['classes'] = _entry(0, plan.max_classes)

    try:
        from accounts.models import CustomUser
        result['utilisateurs'] = _entry(
            CustomUser.objects.filter(is_active=True).count(),
            plan.max_utilisateurs
        )
    except Exception:
        result['utilisateurs'] = _entry(0, plan.max_utilisateurs)

    return result
