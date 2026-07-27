from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import SchoolInfo
from .forms import SchoolInfoForm
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
