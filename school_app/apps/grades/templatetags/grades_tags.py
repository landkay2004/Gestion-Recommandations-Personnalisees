from django import template

register = template.Library()


@register.filter
def get_field(form, eleve_pk):
    """Retourne le champ de note pour un élève donné (saisie_notes form)."""
    field_name = f'note_{eleve_pk}'
    return form[field_name] if field_name in form.fields else ''


@register.filter
def get_item(dictionary, key):
    """Retourne dictionary[key] depuis un template, utile pour les dicts de notes."""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None
