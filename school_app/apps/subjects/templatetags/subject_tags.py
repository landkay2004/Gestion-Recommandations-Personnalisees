from django import template

register = template.Library()


@register.filter
def dict_get(d, key):
    """Récupère une valeur dans un dict par clé (supporte int et str)."""
    if isinstance(d, dict):
        return d.get(key, d.get(str(key), 'bg-secondary'))
    return 'bg-secondary'
