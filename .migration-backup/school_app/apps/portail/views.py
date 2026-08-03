from io import BytesIO
from decimal import Decimal

import qrcode

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone

from accounts.views import prefet_required
from bulletin.models import ModeleBulletin
from classes.models import Classe, AnneeScolaire
from grades.models import Note
from school_settings.models import SchoolInfo
from students.models import Student
from subjects.models import MatiereClasse

from .forms import ActivationForm, AccesManuelForm, CodeAccesForm, PortailConfigForm
from .models import PortailAcces, PortailConfig, PublicationResultats

PERIODES_NORMALES = ['1P', '2P', 'EXAM1', '3P', '4P', 'EXAM2']
PERIODES_LABELS = dict(PublicationResultats.PERIODE_CHOICES)

SESSION_KEY = 'portail_auth'


def _get_acces(eleve):
    acces, _ = PortailAcces.objects.get_or_create(eleve=eleve)
    return acces


def _build_qr_url(request, token):
    config = PortailConfig.get_config()
    base = config.url_portail.rstrip('/') if config.url_portail else request.build_absolute_uri('/').rstrip('/')
    return f"{base}/portail/scan/{token}/"


def _calc_resultats_par_periode(modele, eleve, periodes_a_afficher):
    """Retourne un dict {periode: {label, notes, total_obtenu, total_max, pourcentage, rang}}.

    Optimisations ORM :
    - 1 seule requête pour tous les MatiereClasse de la classe
    - 1 seule requête pour toutes les notes de l'élève (toutes périodes d'un coup)
    - 1 seule requête par période pour les rangs (agrégat par élève)
    """
    resultats = {}
    bms = list(modele.matieres.select_related('matiere').order_by('matiere__maxima', 'ordre'))

    # ── Charger tous les MatiereClasse de la classe en une seule requête ──
    matieres_ids = [bm.matiere_id for bm in bms]
    mc_map = {
        mc.matiere_id: mc
        for mc in MatiereClasse.objects.filter(
            matiere_id__in=matieres_ids, classe=modele.classe
        ).select_related('matiere')
    }
    mc_ids = list(mc_map[mid].pk for mid in mc_map)

    # ── Charger toutes les notes de l'élève en une seule requête ──
    notes_eleve = {}
    for note in Note.objects.filter(
        eleve=eleve,
        matiere_classe__in=list(mc_map.values()),
        periode__in=periodes_a_afficher,
    ).select_related('matiere_classe'):
        notes_eleve[(note.matiere_classe_id, note.periode)] = note.valeur

    for periode in periodes_a_afficher:
        data = {
            'label': PERIODES_LABELS.get(periode, periode),
            'notes': [],
            'total_obtenu': Decimal('0'),
            'total_max': Decimal('0'),
            'pourcentage': 0,
            'rang': '-',
        }
        for bm in bms:
            mc = mc_map.get(bm.matiere_id)
            if mc is None:
                continue                         # matière non affectée à cette classe
            valeur = notes_eleve.get((mc.pk, periode))
            mx = Decimal(str(bm.matiere.maxima))
            data['total_max'] += mx
            if valeur is not None:
                data['total_obtenu'] += valeur
            data['notes'].append({'matiere': bm.matiere, 'note': valeur, 'maxima': bm.matiere.maxima})
        if data['total_max'] > 0:
            data['pourcentage'] = round(float(data['total_obtenu']) / float(data['total_max']) * 100, 2)
        resultats[periode] = data

    # ── Calcul des rangs — 1 requête par période ──
    for periode, data in resultats.items():
        try:
            scores = list(
                Note.objects.filter(matiere_classe__in=mc_ids, periode=periode)
                .values('eleve')
                .annotate(total=Sum('valeur'))
                .order_by('-total')
                .values_list('total', flat=True)
            )
            rang = next(
                (i + 1 for i, s in enumerate(scores)
                 if s is not None and abs(float(s) - float(data['total_obtenu'])) < 0.001),
                '-'
            )
            data['rang'] = rang
        except Exception:
            data['rang'] = '-'

    return resultats


# ─── Portail public ───────────────────────────────────────────────────────────

def portail_accueil(request):
    config = PortailConfig.get_config()
    school = SchoolInfo.get_info()
    from .forms import AccesManuelForm
    form = AccesManuelForm()
    return render(request, 'portail/accueil.html', {
        'config': config, 'school': school, 'form': form,
    })


def portail_acces_manuel(request):
    """Accès manuel au portail : recherche par nom complet + code d'accès."""
    from .forms import AccesManuelForm
    config = PortailConfig.get_config()
    school = SchoolInfo.get_info()

    if request.method != 'POST':
        return redirect('portail_accueil')

    form = AccesManuelForm(request.POST)
    if not form.is_valid():
        return render(request, 'portail/accueil.html', {
            'config': config, 'school': school,
            'form': form, 'show_manual': True,
        })

    nom = form.cleaned_data['nom_complet'].strip()
    code = form.cleaned_data['code']

    # Recherche insensible à la casse par nom complet (nom + postnom + prénom)
    from django.db.models import Q, Value
    from django.db.models.functions import Concat
    from django.db.models import CharField

    acces_qs = PortailAcces.objects.filter(active=True).select_related('eleve')
    match = None
    for acces in acces_qs:
        eleve = acces.eleve
        candidats = [
            eleve.nom_complet,
            f"{eleve.nom} {eleve.prenom}",
            f"{eleve.prenom} {eleve.nom}",
            eleve.nom,
        ]
        if any(nom.lower() == c.lower() for c in candidats if c.strip()):
            if acces.verifier_code(code):
                match = acces
                break

    if match:
        match.tentatives_echec = 0
        match.bloque_jusqu = None
        match.save(update_fields=['tentatives_echec', 'bloque_jusqu'])
        request.session[SESSION_KEY] = str(match.token)
        return redirect('portail_resultats', token=match.token)

    messages.error(request, "Élève introuvable ou code d'accès incorrect. Vérifiez le nom complet et réessayez.")
    return render(request, 'portail/accueil.html', {
        'config': config, 'school': school,
        'form': form, 'show_manual': True,
    })


def portail_scan(request, token):
    acces = get_object_or_404(PortailAcces, token=token)
    config = PortailConfig.get_config()
    school = SchoolInfo.get_info()
    ctx = {'config': config, 'school': school, 'acces': acces}

    if acces.is_bloque():
        return render(request, 'portail/bloque.html', ctx)

    if not acces.active:
        # ── Première utilisation : créer un code d'accès ──
        form = ActivationForm(request.POST or None)
        if request.method == 'POST' and form.is_valid():
            acces.definir_code(form.cleaned_data['code'])
            request.session[SESSION_KEY] = str(acces.token)
            messages.success(request, "Code d'accès créé ! Votre bulletin est maintenant accessible.")
            return redirect('portail_resultats', token=token)
        ctx['form'] = form
        return render(request, 'portail/activation.html', ctx)
    else:
        # ── Connexion : vérifier le code ──
        form = CodeAccesForm(request.POST or None)
        if request.method == 'POST' and form.is_valid():
            if acces.verifier_code(form.cleaned_data['code']):
                acces.tentatives_echec = 0
                acces.bloque_jusqu = None
                acces.save(update_fields=['tentatives_echec', 'bloque_jusqu'])
                request.session[SESSION_KEY] = str(acces.token)
                return redirect('portail_resultats', token=token)
            else:
                acces.incrementer_tentatives()
                if acces.is_bloque():
                    messages.error(request, "Trop de tentatives incorrectes. Accès bloqué 15 minutes.")
                    return redirect('portail_scan', token=token)
                restantes = max(0, 5 - acces.tentatives_echec)
                messages.error(request, f"Code incorrect. {restantes} tentative(s) restante(s).")
        ctx['form'] = form
        return render(request, 'portail/connexion.html', ctx)


def portail_resultats(request, token):
    acces = get_object_or_404(PortailAcces, token=token)
    if request.session.get(SESSION_KEY) != str(acces.token):
        return redirect('portail_scan', token=token)

    config = PortailConfig.get_config()
    school = SchoolInfo.get_info()
    eleve = acces.eleve

    if not eleve.classe:
        return render(request, 'portail/pas_publie.html', {
            'config': config, 'school': school, 'eleve': eleve,
            'message': "Cet élève n'est pas encore affecté à une classe."
        })

    annee = eleve.classe.annee_scolaire
    periodes_publiees = set(
        PublicationResultats.objects.filter(
            classe=eleve.classe, annee_scolaire=annee, publie=True
        ).values_list('periode', flat=True)
    )

    if not periodes_publiees:
        return render(request, 'portail/pas_publie.html', {
            'config': config, 'school': school, 'eleve': eleve,
            'message': "Aucun résultat n'a encore été publié pour votre classe."
        })

    try:
        modele = ModeleBulletin.objects.get(classe=eleve.classe, annee_scolaire=annee)
    except ModeleBulletin.DoesNotExist:
        return render(request, 'portail/pas_publie.html', {
            'config': config, 'school': school, 'eleve': eleve,
            'message': "Le modèle de bulletin de cette classe n'est pas encore configuré."
        })

    periodes_a_afficher = [p for p in PERIODES_NORMALES if p in periodes_publiees]
    resultats = _calc_resultats_par_periode(modele, eleve, periodes_a_afficher)

    # ── Résumés de semestres ─────────────────────────────────────────────────
    resume_s1 = None
    resume_s2 = None
    resultat_annuel = None

    s1_complet = periodes_publiees >= {'1P', '2P', 'EXAM1'}
    s2_complet = periodes_publiees >= {'3P', '4P', 'EXAM2'}
    annuel_publie = 'ANNUEL' in periodes_publiees

    if s1_complet or s2_complet or annuel_publie:
        try:
            from bulletin.pdf_views import (
                _calc_eleve as _pdf_calc,
                _get_classement as _pdf_rang,
                _get_classement_semestres as _pdf_sem_rang,
            )
            _, total_annuel, max_annuel, pct_annuel, total_s1, total_s2 = _pdf_calc(modele, eleve)
            max_sem = max_annuel / 2 if max_annuel else Decimal('0')
            nb_eleves = eleve.classe.eleves.count()

            if s1_complet or s2_complet:
                rang_s1, rang_s2 = _pdf_sem_rang(modele, total_s1, total_s2)
                if s1_complet and max_sem:
                    pct_s1 = round(float(total_s1) / float(max_sem) * 100, 1)
                    resume_s1 = {'total': total_s1, 'max': max_sem, 'pourcentage': pct_s1, 'rang': rang_s1}
                if s2_complet and max_sem:
                    pct_s2 = round(float(total_s2) / float(max_sem) * 100, 1)
                    resume_s2 = {'total': total_s2, 'max': max_sem, 'pourcentage': pct_s2, 'rang': rang_s2}

            if s1_complet and s2_complet:
                rang_annuel = _pdf_rang(modele, total_annuel)
                resultat_annuel = {
                    'total': total_annuel, 'max': max_annuel,
                    'pourcentage': pct_annuel, 'rang': rang_annuel,
                }
        except Exception:
            pass

    nb_eleves = eleve.classe.eleves.count()

    # Vérifier s'il y a un historique (années passées avec notes)
    has_archives = Note.objects.filter(
        eleve=eleve
    ).exclude(
        matiere_classe__classe__annee_scolaire=annee
    ).exists()

    return render(request, 'portail/resultats.html', {
        'config': config, 'school': school, 'eleve': eleve,
        'acces': acces,
        'modele': modele,
        'resultats': resultats,
        'resume_s1': resume_s1,
        'resume_s2': resume_s2,
        'resultat_annuel': resultat_annuel,
        'nb_eleves': nb_eleves,
        'annee': annee,
        'has_archives': has_archives,
    })


def portail_archives(request, token):
    """Liste les années scolaires archivées (clôturées) pour un élève."""
    acces = get_object_or_404(PortailAcces, token=token)
    if request.session.get(SESSION_KEY) != str(acces.token):
        return redirect('portail_scan', token=token)

    config = PortailConfig.get_config()
    school = SchoolInfo.get_info()
    eleve = acces.eleve

    # Trouver toutes les années où l'élève a des notes publiées, excluant l'année courante
    annee_courante = eleve.classe.annee_scolaire if eleve.classe else None

    # Récupérer les classes historiques via les notes
    classes_avec_notes = Classe.objects.filter(
        matieres__notes__eleve=eleve
    ).select_related('annee_scolaire', 'section', 'niveau').distinct().order_by('-annee_scolaire__annee')

    archives = []
    for classe in classes_avec_notes:
        if annee_courante and classe.annee_scolaire == annee_courante:
            continue
        # Vérifier qu'il y a des résultats publiés
        periodes_pub = PublicationResultats.objects.filter(
            classe=classe, annee_scolaire=classe.annee_scolaire, publie=True
        ).values_list('periode', flat=True)
        if periodes_pub.exists():
            archives.append({
                'annee': classe.annee_scolaire,
                'classe': classe,
                'periodes_publiees': list(periodes_pub),
                'cloturee': classe.annee_scolaire.cloturee,
            })

    return render(request, 'portail/archives.html', {
        'config': config, 'school': school, 'eleve': eleve,
        'acces': acces,
        'archives': archives,
        'annee_courante': annee_courante,
    })


def portail_archives_annee(request, token, annee_id):
    """Affiche les résultats d'une année archivée pour un élève."""
    acces = get_object_or_404(PortailAcces, token=token)
    if request.session.get(SESSION_KEY) != str(acces.token):
        return redirect('portail_scan', token=token)

    config = PortailConfig.get_config()
    school = SchoolInfo.get_info()
    eleve = acces.eleve
    annee = get_object_or_404(AnneeScolaire, pk=annee_id)

    # Trouver la classe de l'élève pour cette année (via ses notes)
    try:
        classe = Classe.objects.filter(
            matieres__notes__eleve=eleve,
            annee_scolaire=annee,
        ).select_related('section', 'niveau').distinct().first()
    except Exception:
        classe = None

    if not classe:
        return render(request, 'portail/pas_publie.html', {
            'config': config, 'school': school, 'eleve': eleve,
            'message': f"Aucune donnée trouvée pour l'année {annee}."
        })

    periodes_publiees = set(
        PublicationResultats.objects.filter(
            classe=classe, annee_scolaire=annee, publie=True
        ).values_list('periode', flat=True)
    )

    if not periodes_publiees:
        return render(request, 'portail/pas_publie.html', {
            'config': config, 'school': school, 'eleve': eleve,
            'message': f"Aucun résultat publié pour l'année {annee}."
        })

    try:
        modele = ModeleBulletin.objects.get(classe=classe, annee_scolaire=annee)
    except ModeleBulletin.DoesNotExist:
        return render(request, 'portail/pas_publie.html', {
            'config': config, 'school': school, 'eleve': eleve,
            'message': f"Le bulletin de l'année {annee} n'est pas disponible."
        })

    periodes_a_afficher = [p for p in PERIODES_NORMALES if p in periodes_publiees]
    resultats = _calc_resultats_par_periode(modele, eleve, periodes_a_afficher)

    resume_s1 = None
    resume_s2 = None
    resultat_annuel = None
    s1_complet = periodes_publiees >= {'1P', '2P', 'EXAM1'}
    s2_complet = periodes_publiees >= {'3P', '4P', 'EXAM2'}

    if s1_complet or s2_complet:
        try:
            from bulletin.pdf_views import (
                _calc_eleve as _pdf_calc,
                _get_classement as _pdf_rang,
                _get_classement_semestres as _pdf_sem_rang,
            )
            _, total_annuel, max_annuel, pct_annuel, total_s1, total_s2 = _pdf_calc(modele, eleve)
            max_sem = max_annuel / 2 if max_annuel else Decimal('0')
            if s1_complet or s2_complet:
                rang_s1, rang_s2 = _pdf_sem_rang(modele, total_s1, total_s2)
                if s1_complet and max_sem:
                    pct_s1 = round(float(total_s1) / float(max_sem) * 100, 1)
                    resume_s1 = {'total': total_s1, 'max': max_sem, 'pourcentage': pct_s1, 'rang': rang_s1}
                if s2_complet and max_sem:
                    pct_s2 = round(float(total_s2) / float(max_sem) * 100, 1)
                    resume_s2 = {'total': total_s2, 'max': max_sem, 'pourcentage': pct_s2, 'rang': rang_s2}
            if s1_complet and s2_complet:
                rang_annuel = _pdf_rang(modele, total_annuel)
                resultat_annuel = {
                    'total': total_annuel, 'max': max_annuel,
                    'pourcentage': pct_annuel, 'rang': rang_annuel,
                }
        except Exception:
            pass

    nb_eleves = classe.eleves.count()

    return render(request, 'portail/archives_annee.html', {
        'config': config, 'school': school, 'eleve': eleve,
        'acces': acces,
        'modele': modele,
        'classe': classe,
        'resultats': resultats,
        'resume_s1': resume_s1,
        'resume_s2': resume_s2,
        'resultat_annuel': resultat_annuel,
        'nb_eleves': nb_eleves,
        'annee': annee,
    })


def portail_bulletin_pdf(request, token):
    """Portail parents : téléchargement du bulletin PDF via token (session requise)."""
    acces = get_object_or_404(PortailAcces, token=token)
    if request.session.get(SESSION_KEY) != str(acces.token):
        return redirect('portail_scan', token=token)

    eleve = acces.eleve
    if not eleve.classe:
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest("Élève sans classe.")

    annee = eleve.classe.annee_scolaire
    try:
        modele = ModeleBulletin.objects.get(classe=eleve.classe, annee_scolaire=annee)
    except ModeleBulletin.DoesNotExist:
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest("Bulletin non configuré pour cette classe.")

    periodes_pub = set(
        PublicationResultats.objects.filter(
            classe=eleve.classe, annee_scolaire=annee, publie=True
        ).values_list('periode', flat=True)
    )
    if not (periodes_pub >= {'1P', '2P', 'EXAM1', '3P', '4P', 'EXAM2'}):
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest(
            "Les deux semestres doivent être publiés pour télécharger le bulletin."
        )

    from bulletin.pdf_views import build_bulletin_pdf_response
    return build_bulletin_pdf_response(modele, eleve)


def portail_deconnexion(request, token):
    request.session.pop(SESSION_KEY, None)
    return redirect('portail_scan', token=token)


# ─── QR Code image ────────────────────────────────────────────────────────────

def qr_code_image(request, pk):
    """Renvoie l'image PNG du QR Code d'un élève (accessible Préfet + carte)."""
    eleve = get_object_or_404(Student, pk=pk)
    acces = _get_acces(eleve)
    url = _build_qr_url(request, acces.token)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10, border=3,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = BytesIO()
    img.save(buf, format='PNG')
    return HttpResponse(buf.getvalue(), content_type='image/png')


# ─── Back-office Préfet ───────────────────────────────────────────────────────

@login_required
@prefet_required
def publication_list(request):
    annee = AnneeScolaire.objects.filter(active=True).first()
    classes = (
        Classe.objects.filter(annee_scolaire=annee).select_related('section', 'niveau')
        if annee else []
    )
    PERIODES = PublicationResultats.PERIODE_CHOICES

    grille = []
    for classe in classes:
        pubs = {
            p.periode: p
            for p in PublicationResultats.objects.filter(classe=classe, annee_scolaire=annee)
        }
        ligne = []
        for code, label in PERIODES:
            pub = pubs.get(code)
            ligne.append({
                'code': code, 'label': label,
                'pub': pub,
                'publie': pub.publie if pub else False,
            })
        grille.append({'classe': classe, 'periodes': ligne})

    return render(request, 'portail/publication_list.html', {
        'grille': grille,
        'periodes': PERIODES,
        'annee': annee,
    })


@login_required
@prefet_required
def publication_toggle(request, classe_id, periode):
    annee = get_object_or_404(AnneeScolaire, active=True)
    classe = get_object_or_404(Classe, pk=classe_id)
    pub, _ = PublicationResultats.objects.get_or_create(
        classe=classe, annee_scolaire=annee, periode=periode,
        defaults={'publie': False}
    )
    if pub.publie:
        pub.depublier()
        messages.success(request, f"Dépublié : {classe} — {pub.get_periode_display()}")
    else:
        pub.publier(request.user)
        messages.success(request, f"Publié : {classe} — {pub.get_periode_display()}")
    return redirect('publication_list')


@login_required
@prefet_required
def portail_config_view(request):
    config = PortailConfig.get_config()
    form = PortailConfigForm(request.POST or None, request.FILES or None, instance=config)
    if form.is_valid():
        form.save()
        messages.success(request, "Configuration du portail enregistrée.")
        return redirect('portail_config')
    return render(request, 'portail/config.html', {'form': form, 'config': config})


@login_required
@prefet_required
def reset_acces_eleve(request, pk):
    eleve = get_object_or_404(Student, pk=pk)
    acces, created = PortailAcces.objects.get_or_create(eleve=eleve)
    if not created and acces.active:
        acces.reset_acces()
        messages.success(request, f"Accès portail réinitialisé pour {eleve.nom_complet}. Le parent devra créer un nouveau code.")
    else:
        messages.info(request, f"L'accès de {eleve.nom_complet} n'était pas encore activé.")
    return redirect('student_detail', pk=pk)


@login_required
@prefet_required
def acces_list(request):
    """Liste tous les élèves avec leur statut d'accès portail."""
    annee = AnneeScolaire.objects.filter(active=True).first()
    classe_id = request.GET.get('classe', '')
    eleves = Student.objects.select_related('classe', 'classe__section', 'portail_acces')
    if classe_id:
        eleves = eleves.filter(classe_id=classe_id)
    elif annee:
        eleves = eleves.filter(classe__annee_scolaire=annee)
    classes = Classe.objects.filter(annee_scolaire=annee).select_related('section') if annee else []
    return render(request, 'portail/acces_list.html', {
        'eleves': eleves, 'classes': classes, 'classe_id': classe_id, 'annee': annee,
    })
