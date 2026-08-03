from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import json
from .models import SchoolInfo, MatriculeConfig
from .forms import SchoolInfoForm, MatriculeConfigForm
from accounts.views import prefet_required


def _prefet_or_admin_required(view_func):
    """Autorise préfet ET administrateur d'école."""
    from functools import wraps
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not (request.user.is_prefet() or request.user.is_admin_ecole()):
            from django.contrib import messages as _msgs
            _msgs.error(request, "Accès réservé au préfet ou à l'administrateur.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@_prefet_or_admin_required
def settings_view(request):
    info = SchoolInfo.get_info()
    form = SchoolInfoForm(request.POST or None, request.FILES or None, instance=info)
    if form.is_valid():
        form.save()
        messages.success(request, "Paramètres enregistrés.")
        return redirect('settings_view')
    return render(request, 'school_settings/settings.html', {'form': form, 'info': info})


def _manifest_ctx(info):
    """Contexte commun aux deux manifests : vérifie si les icônes générées existent."""
    return {
        'info': info,
        'icons_generated': info.pwa_icons_exist(),
        'icons_base_url':  info.pwa_icons_base_url(),
    }


def manifest_view(request):
    """PWA manifest pour le back-office (start_url = /)."""
    info = SchoolInfo.get_info()
    content = render_to_string('manifest.json', _manifest_ctx(info), request=request)
    return HttpResponse(content, content_type='application/manifest+json')


def manifest_portail_view(request):
    """PWA manifest pour le portail parent (start_url = /portail/)."""
    info = SchoolInfo.get_info()
    content = render_to_string('manifest_portail.json', _manifest_ctx(info), request=request)
    return HttpResponse(content, content_type='application/manifest+json')


@login_required
@_prefet_or_admin_required
def matricule_config_view(request):
    """Configure le format de matriculation automatique des élèves."""
    from django.http import JsonResponse
    config = MatriculeConfig.get_config()
    form = MatriculeConfigForm(request.POST or None, instance=config)
    if form.is_valid():
        form.save()
        messages.success(request, "Configuration de la matriculation enregistrée.")
        return redirect('matricule_config')
    apercu = config.apercu()
    return render(request, 'school_settings/matricule_config.html', {
        'form': form,
        'config': config,
        'apercu': apercu,
    })


@login_required
@_prefet_or_admin_required
def matricule_apercu_ajax(request):
    """Endpoint AJAX : retourne un aperçu du matricule selon le format soumis."""
    from django.http import JsonResponse
    fmt = request.GET.get('format', '')
    prefixe = request.GET.get('prefixe', 'EL')
    try:
        compteur_str = request.GET.get('compteur', '0')
        compteur = max(0, int(compteur_str))
    except (ValueError, TypeError):
        compteur = 0

    config = MatriculeConfig(
        format_matricule=fmt or '{PREFIXE}{ANNEE2}{SEQ4}',
        prefixe=prefixe or 'EL',
        compteur=compteur,
    )
    try:
        apercu = config.apercu()
    except Exception as exc:
        return JsonResponse({'apercu': '', 'error': str(exc)})
    return JsonResponse({'apercu': apercu})


def favicon_view(request):
    """Sert le favicon depuis le logo de l'école ou l'icône générée."""
    from django.http import HttpResponseRedirect
    from django.templatetags.static import static
    info = SchoolInfo.get_info()
    if info.pwa_icons_exist():
        return HttpResponseRedirect(info.pwa_icons_base_url() + '/favicon.png')
    if info.logo:
        return HttpResponseRedirect(info.logo.url)
    return HttpResponseRedirect(static('icons/icon-72.png'))
