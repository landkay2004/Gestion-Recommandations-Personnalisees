import base64
from io import BytesIO

import qrcode

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from accounts.views import prefet_required
from classes.models import Classe, AnneeScolaire
from portail.models import PortailAcces, PortailConfig
from school_settings.models import SchoolInfo
from students.models import Student
from .models import CarteConfig


def _get_acces(eleve):
    acces, _ = PortailAcces.objects.get_or_create(eleve=eleve)
    return acces


def _qr_base64(request, eleve):
    acces = _get_acces(eleve)
    config = PortailConfig.get_config()
    base_url = config.url_portail.rstrip('/') if config.url_portail else request.build_absolute_uri('/').rstrip('/')
    url = f"{base_url}/portail/scan/{acces.token}/"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=6, border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode()


@login_required
@prefet_required
def carte_list(request):
    annee     = AnneeScolaire.objects.filter(active=True).first()
    config    = CarteConfig.get_config()
    classe_id = request.GET.get('classe', '')
    classes   = Classe.objects.filter(annee_scolaire=annee).select_related('section') if annee else []
    eleves    = Student.objects.select_related('classe', 'classe__section')
    if classe_id:
        eleves = eleves.filter(classe_id=classe_id)
    elif annee:
        eleves = eleves.filter(classe__annee_scolaire=annee)
    return render(request, 'carte_eleve/liste.html', {
        'eleves': eleves, 'classes': classes,
        'classe_id': classe_id, 'annee': annee,
        'config': config,
    })


@login_required
@prefet_required
def carte_preview(request, pk):
    eleve  = get_object_or_404(Student, pk=pk)
    school = SchoolInfo.get_info()
    config = CarteConfig.get_config()
    qr_b64 = _qr_base64(request, eleve)
    return render(request, 'carte_eleve/carte_single.html', {
        'eleves_data': [{'eleve': eleve, 'qr_b64': qr_b64}],
        'school': school, 'config': config,
        'annee': eleve.classe.annee_scolaire if eleve.classe else None,
        'mode': 'preview',
        'titre': f"Carte de {eleve.nom_complet}",
    })


@login_required
@prefet_required
def cartes_classe(request, classe_id):
    classe = get_object_or_404(Classe, pk=classe_id)
    school = SchoolInfo.get_info()
    config = CarteConfig.get_config()

    LOT = 20
    try:
        page = max(1, int(request.GET.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    offset = (page - 1) * LOT

    eleves_qs  = Student.objects.filter(classe=classe).order_by('nom', 'postnom')
    total      = eleves_qs.count()
    eleves_lot = eleves_qs[offset:offset + LOT]

    eleves_data = [{'eleve': e, 'qr_b64': _qr_base64(request, e)} for e in eleves_lot]

    nb_pages = (total + LOT - 1) // LOT
    return render(request, 'carte_eleve/carte_single.html', {
        'eleves_data': eleves_data, 'school': school, 'config': config,
        'annee': classe.annee_scolaire, 'mode': 'print',
        'titre': f"Cartes — {classe}",
        'page': page, 'nb_pages': nb_pages, 'total': total,
        'page_suivante':   page + 1 if page < nb_pages else None,
        'page_precedente': page - 1 if page > 1 else None,
        'classe_id': classe_id,
    })


@login_required
@prefet_required
def carte_config(request):
    config = CarteConfig.get_config()
    school = SchoolInfo.get_info()
    annee  = AnneeScolaire.objects.filter(active=True).first()

    # Élève exemple pour l'aperçu
    sample_eleve = Student.objects.select_related('classe').first()
    sample_qr    = _qr_base64(request, sample_eleve) if sample_eleve else None

    if request.method == 'POST':
        config.modele             = request.POST.get('modele', config.modele)
        config.couleur_principale = request.POST.get('couleur_principale', config.couleur_principale)
        config.couleur_secondaire = request.POST.get('couleur_secondaire', config.couleur_secondaire)
        config.devise             = request.POST.get('devise', config.devise)

        config.afficher_photo     = 'afficher_photo'     in request.POST
        config.afficher_matricule = 'afficher_matricule' in request.POST
        config.afficher_classe    = 'afficher_classe'    in request.POST
        config.afficher_annee     = 'afficher_annee'     in request.POST
        config.afficher_qr        = 'afficher_qr'        in request.POST
        config.afficher_ddn       = 'afficher_ddn'       in request.POST
        config.afficher_sexe      = 'afficher_sexe'      in request.POST

        # Gestion des fichiers
        for field in ('logo_override', 'signature_prefet', 'signature_directeur', 'cachet'):
            if field in request.FILES:
                setattr(config, field, request.FILES[field])
            elif f'{field}_clear' in request.POST:
                setattr(config, field, None)

        config.save()
        messages.success(request, '✅ Configuration des cartes mise à jour avec succès.')
        return redirect('carte_list')

    presets = [
        ('Classique',      '#1e3a5f', '#2563eb'),
        ('Moderne',        '#1e40af', '#3b82f6'),
        ('Vert institution', '#14532d', '#d97706'),
        ('Ardoise',        '#1e293b', '#38bdf8'),
        ('Bordeaux',       '#7f1d1d', '#dc2626'),
        ('Premium',        '#1c1917', '#d97706'),
        ('Violet',         '#4c1d95', '#8b5cf6'),
        ('Teal',           '#134e4a', '#14b8a6'),
    ]

    fields_visibility = [
        ('afficher_photo',     'Photo de l\'élève',   config.afficher_photo),
        ('afficher_matricule', 'Matricule',            config.afficher_matricule),
        ('afficher_classe',    'Classe',               config.afficher_classe),
        ('afficher_annee',     'Année scolaire',       config.afficher_annee),
        ('afficher_qr',        'QR Code',              config.afficher_qr),
        ('afficher_ddn',       'Date de naissance',    config.afficher_ddn),
        ('afficher_sexe',      'Sexe',                 config.afficher_sexe),
    ]

    sig_fields = [
        ('signature_directeur', 'Signature du directeur', config.signature_directeur if config.signature_directeur else None),
        ('signature_prefet',    'Signature du préfet',    config.signature_prefet    if config.signature_prefet    else None),
        ('cachet',              'Cachet de l\'établissement', config.cachet if config.cachet else None),
    ]

    return render(request, 'carte_eleve/carte_config.html', {
        'config':             config,
        'school':             school,
        'annee':              annee,
        'sample_eleve':       sample_eleve,
        'sample_qr':          sample_qr,
        'presets':            presets,
        'fields_visibility':  fields_visibility,
        'sig_fields':         sig_fields,
    })
