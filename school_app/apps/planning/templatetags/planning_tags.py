from django import template

register = template.Library()


@register.filter
def dict_get(d, key):
    """Retourne d[key] depuis un dict dans un template Django."""
    if isinstance(d, dict):
        return d.get(key)
    return None
