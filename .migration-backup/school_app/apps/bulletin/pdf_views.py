"""
Génération PDF du bulletin individuel au format officiel IGE/P.S/005.
En-tête: Drapeau RDC | Titre ministère | Armoiries
Reproduit fidèlement le formulaire officiel de la RDC.
"""
import os
from io import BytesIO
from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.conf import settings

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, Image
)

from .models import ModeleBulletin
from students.models import Student
from grades.models import Note
from subjects.models import MatiereClasse
from school_settings.models import SchoolInfo


# ─── Palette officielle ───────────────────────────────────────────────────────
BLACK     = colors.black
WHITE     = colors.white
GREY_HDR  = colors.HexColor('#D0D0D0')   # fond en-têtes colonnes
GREY_MAX  = colors.HexColor('#B8B8B8')   # fond lignes MAXIMA
GREY_BG   = colors.HexColor('#E8E8E8')   # fond lignes bilan (application, conduite…)
BLUE_HDR  = colors.HexColor('#00008B')   # bleu foncé titre ministère (optionnel)


def _note_str(val):
    """Affiche une note arrondie à l'entier (sans décimale)."""
    if val is None:
        return ''
    return str(int(round(float(val))))


def _calc_eleve(modele, eleve):
    """Calcule les notes de l'élève selon la formule officielle du bulletin.

    Retourne : (matieres_data, total_obtenu, total_max_tg, pct, total_s1, total_s2)
    total_s1 = somme des TOT S1 (1P+2P+EXAM1) sur toutes les matières
    total_s2 = somme des TOT S2 (3P+4P+EXAM2) sur toutes les matières
    NOTA : cette fonction est la SOURCE DE VÉRITÉ du portail parents pour le résultat annuel.
    """
    periodes = ['1P', '2P', 'EXAM1', '3P', '4P', 'EXAM2', 'REPECHAGE']
    matieres_data = []
    total_obtenu = Decimal('0')
    total_max_tg = Decimal('0')
    total_s1     = Decimal('0')
    total_s2     = Decimal('0')

    bms = list(modele.matieres.select_related('matiere').order_by('matiere__maxima', 'ordre'))
    matiere_ids = [bm.matiere_id for bm in bms]

    # Fetch all MatiereClasse in one query instead of one per matière
    mc_map = {mc.matiere_id: mc for mc in MatiereClasse.objects.filter(
        matiere_id__in=matiere_ids, classe=modele.classe
    )}

    # Fetch all notes for this student in one query instead of 7 per matière
    notes_index = {}
    if mc_map:
        for n in Note.objects.filter(
            eleve=eleve,
            matiere_classe_id__in=[mc.pk for mc in mc_map.values()]
        ).values('matiere_classe_id', 'periode', 'valeur'):
            notes_index[(n['matiere_classe_id'], n['periode'])] = n['valeur']

    for bm in bms:
        mat = bm.matiere
        mc = mc_map.get(mat.id)
        notes_dict = {}
        if mc:
            for p in periodes:
                notes_dict[p] = notes_index.get((mc.pk, p))
        else:
            for p in periodes:
                notes_dict[p] = None

        mx  = mat.maxima
        n1p = notes_dict.get('1P')    or Decimal('0')
        n2p = notes_dict.get('2P')    or Decimal('0')
        ne1 = notes_dict.get('EXAM1') or Decimal('0')
        n3p = notes_dict.get('3P')    or Decimal('0')
        n4p = notes_dict.get('4P')    or Decimal('0')
        ne2 = notes_dict.get('EXAM2') or Decimal('0')

        has_s1 = any(notes_dict.get(p) is not None for p in ('1P', '2P', 'EXAM1'))
        has_s2 = any(notes_dict.get(p) is not None for p in ('3P', '4P', 'EXAM2'))

        tot_s1 = (n1p + n2p + ne1) if has_s1 else None
        tot_s2 = (n3p + n4p + ne2) if has_s2 else None
        tg     = (tot_s1 or Decimal('0')) + (tot_s2 or Decimal('0'))
        max_tg = Decimal(mx) * 8

        total_obtenu += tg
        total_max_tg += max_tg
        total_s1     += (tot_s1 or Decimal('0'))
        total_s2     += (tot_s2 or Decimal('0'))

        matieres_data.append({
            'matiere':   mat,
            'n1p':       notes_dict.get('1P'),
            'n2p':       notes_dict.get('2P'),
            'nexam1':    notes_dict.get('EXAM1'),
            'tot_s1':    tot_s1,
            'n3p':       notes_dict.get('3P'),
            'n4p':       notes_dict.get('4P'),
            'nexam2':    notes_dict.get('EXAM2'),
            'tot_s2':    tot_s2,
            'tg':        tg,
            'repechage': notes_dict.get('REPECHAGE'),
        })

    pct = round(float(total_obtenu) / float(total_max_tg) * 100, 1) if total_max_tg else 0
    return matieres_data, total_obtenu, total_max_tg, pct, total_s1, total_s2


def _get_classement(modele, eleve_score):
    """Classement annuel (hors repêchage) — une seule requête d'agrégation."""
    from django.db.models import Sum
    scores = list(
        Note.objects.filter(
            eleve__classe=modele.classe,
            matiere_classe__classe=modele.classe,
        ).exclude(periode='REPECHAGE')
        .values('eleve')
        .annotate(total=Sum('valeur'))
        .order_by('-total')
        .values_list('total', flat=True)
    )
    scores.sort(reverse=True)
    try:
        return scores.index(eleve_score) + 1
    except ValueError:
        return '-'


def _get_classement_semestres(modele, s1_score, s2_score):
    """Retourne (rang_s1, rang_s2) dans la classe — deux requêtes d'agrégation."""
    from django.db.models import Sum
    base_qs = Note.objects.filter(
        eleve__classe=modele.classe,
        matiere_classe__classe=modele.classe,
    ).values('eleve')

    scores_s1 = list(
        base_qs.filter(periode__in=['1P', '2P', 'EXAM1'])
        .annotate(t=Sum('valeur')).order_by('-t').values_list('t', flat=True)
    )
    scores_s2 = list(
        base_qs.filter(periode__in=['3P', '4P', 'EXAM2'])
        .annotate(t=Sum('valeur')).order_by('-t').values_list('t', flat=True)
    )
    rang_s1 = scores_s1.index(s1_score) + 1 if s1_score in scores_s1 else '-'
    rang_s2 = scores_s2.index(s2_score) + 1 if s2_score in scores_s2 else '-'
    return rang_s1, rang_s2


def _calc_per_periode(modele, eleve):
    """Calcule total et rang par période individuelle (pour TOTAUX/POURCENTAGE/PLACE)."""
    from django.db.models import Sum

    bms = list(modele.matieres.select_related('matiere'))
    matiere_ids = [bm.matiere_id for bm in bms]
    mc_ids = list(MatiereClasse.objects.filter(
        matiere_id__in=matiere_ids, classe=modele.classe
    ).values_list('pk', flat=True))

    periodes = ['1P', '2P', 'EXAM1', '3P', '4P', 'EXAM2']
    result = {}
    for periode in periodes:
        total_p = Note.objects.filter(
            eleve=eleve, matiere_classe_id__in=mc_ids, periode=periode
        ).aggregate(t=Sum('valeur'))['t'] or Decimal('0')

        scores = list(
            Note.objects.filter(matiere_classe_id__in=mc_ids, periode=periode)
            .values('eleve').annotate(t=Sum('valeur')).order_by('-t')
            .values_list('t', flat=True)
        )
        rang = next(
            (i + 1 for i, s in enumerate(scores)
             if s is not None and abs(float(s) - float(total_p)) < 0.01),
            '-'
        )
        result[periode] = {'total': total_p, 'rang': rang}
    return result


def _mention(pct):
    if pct >= 80: return 'Grande distinction'
    if pct >= 70: return 'Distinction'
    if pct >= 60: return 'Satisfaction'
    if pct >= 50: return 'Réussite'
    return 'Échec'


def _logo_path(filename):
    """Chemin absolu vers un fichier static/images/."""
    return os.path.join(settings.BASE_DIR, 'static', 'images', filename)


# ─── Styles ───────────────────────────────────────────────────────────────────
def _styles():
    base = getSampleStyleSheet()
    tiny  = ParagraphStyle('tiny',  parent=base['Normal'], fontSize=6,   leading=7.5)
    small = ParagraphStyle('small', parent=base['Normal'], fontSize=7,   leading=8.5)
    bold  = ParagraphStyle('bold',  parent=base['Normal'], fontSize=7,   leading=8.5, fontName='Helvetica-Bold')
    ctr   = ParagraphStyle('ctr',   parent=base['Normal'], fontSize=6.5, leading=8,   alignment=TA_CENTER)
    ctr_b = ParagraphStyle('ctr_b', parent=base['Normal'], fontSize=6.5, leading=8,   alignment=TA_CENTER, fontName='Helvetica-Bold')
    min_t = ParagraphStyle('min_t', parent=base['Normal'], fontSize=8,   leading=10,  fontName='Helvetica-Bold', alignment=TA_CENTER)
    titre = ParagraphStyle('titre', parent=base['Normal'], fontSize=7.5, leading=9.5, fontName='Helvetica-Bold', alignment=TA_CENTER)
    right = ParagraphStyle('right', parent=base['Normal'], fontSize=6,   leading=7.5, alignment=TA_RIGHT)
    return tiny, small, bold, ctr, ctr_b, min_t, titre, right


# ─── Vue principale ───────────────────────────────────────────────────────────
def build_bulletin_pdf_response(modele, eleve, school=None):
    """Génère et retourne la réponse HTTP PDF du bulletin.

    Appelable par toute vue authentifiée (back-office ET portail parents).
    Si school est None, récupère SchoolInfo automatiquement.
    """
    if school is None:
        school = SchoolInfo.get_info()

    matieres_data, total_obtenu, total_max, pct, total_s1, total_s2 = _calc_eleve(modele, eleve)
    classement          = _get_classement(modele, total_obtenu)
    rang_s1, rang_s2    = _get_classement_semestres(modele, total_s1, total_s2)
    nb_eleves           = eleve.classe.eleves.count() if eleve.classe else 0
    mention             = _mention(pct)
    max_sem             = total_max / 2 if total_max else Decimal('0')
    pct_s1 = round(float(total_s1) / float(max_sem) * 100, 1) if max_sem else 0
    pct_s2 = round(float(total_s2) / float(max_sem) * 100, 1) if max_sem else 0

    pp     = _calc_per_periode(modele, eleve)
    max_p  = float(total_max) / 8   # maxima d'une période normale
    max_e  = float(total_max) / 4   # maxima d'une période examen (× 2)

    def _pct(tot, mx):
        if not mx: return ''
        return f"{round(float(tot) / mx * 100, 1)}%"

    buf = BytesIO()
    page_w, page_h = A4
    avail_w = page_w - 2.4 * cm

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.2*cm, rightMargin=1.2*cm,
        topMargin=0.8*cm,  bottomMargin=0.8*cm,
        title=f"Bulletin {eleve.nom} {eleve.postnom}",
    )
    tiny, small, bold, ctr, ctr_b, min_t, titre, right = _styles()
    story = []

    # ══════════════════════════════════════════════════════════════════════════
    # 1. EN-TÊTE OFFICIELLE : Drapeau | Titre Ministère | Armoiries
    # ══════════════════════════════════════════════════════════════════════════
    logo_h = 2.0 * cm

    drapeau_path  = _logo_path('drapeau.png')
    armoiries_path = _logo_path('armoiries.png')

    try:
        img_drapeau   = Image(drapeau_path,  width=2.6*cm, height=logo_h)
    except Exception:
        img_drapeau   = Paragraph('', small)

    try:
        img_armoiries = Image(armoiries_path, width=2.0*cm, height=logo_h)
    except Exception:
        img_armoiries = Paragraph('', small)

    ministere_txt = (
        "REPUBLIQUE DEMOCRATIQUE DU CONGO<br/>"
        "MINISTERE DE L'EDUCATION NATIONALE<br/>"
        "ET NOUVELLE CITOYENNETE"
    )

    header_data = [[
        img_drapeau,
        Paragraph(ministere_txt, min_t),
        img_armoiries,
    ]]
    col_logo = 2.8 * cm
    header_tbl = Table(
        header_data,
        colWidths=[col_logo, avail_w - 2 * col_logo, col_logo]
    )
    header_tbl.setStyle(TableStyle([
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',       (0, 0), (0, 0),   'LEFT'),
        ('ALIGN',       (1, 0), (1, 0),   'CENTER'),
        ('ALIGN',       (2, 0), (2, 0),   'RIGHT'),
        ('BOX',         (0, 0), (-1, -1), 0.8, BLACK),
        ('TOPPADDING',  (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',(0,0), (-1, -1), 3),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 1*mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 2. NUMÉRO D'IDENTIFICATION (N° ID.)
    # ══════════════════════════════════════════════════════════════════════════
    id_code = school.code if school else ''
    # Découper code en caractères individuels pour les cases
    chars = list(id_code.replace('/', '-').replace(' ', ''))[:20]
    # Cellules pour chaque caractère
    cases = [Paragraph(f"<b>{c}</b>", ctr_b) for c in chars]
    # Remplir à 20 cases
    while len(cases) < 20:
        cases.append(Paragraph('', ctr))

    id_label = [Paragraph('<b>N° ID.</b>', bold)]
    id_row   = [id_label + cases]
    case_w   = (avail_w - 1.8*cm) / 20
    id_tbl   = Table(id_row, colWidths=[1.8*cm] + [case_w]*20)
    id_tbl.setStyle(TableStyle([
        ('BOX',          (0, 0), (-1, -1), 0.8, BLACK),
        ('GRID',         (1, 0), (-1, -1), 0.5, BLACK),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',        (0, 0), (0,  0),  'LEFT'),
        ('ALIGN',        (1, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE',     (0, 0), (-1, -1), 6.5),
        ('TOPPADDING',   (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 2),
        ('LEFTPADDING',  (0, 0), (0, 0),   4),
    ]))
    story.append(id_tbl)
    story.append(Spacer(1, 1*mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 3. PROVINCE
    # ══════════════════════════════════════════════════════════════════════════
    prov_txt = f"<b>PROVINCE DU {(school.province or '').upper()}</b>" if school else '<b>PROVINCE :</b>'
    prov_tbl = Table([[Paragraph(prov_txt, bold)]], colWidths=[avail_w])
    prov_tbl.setStyle(TableStyle([
        ('BOX',         (0,0), (-1,-1), 0.8, BLACK),
        ('TOPPADDING',  (0,0), (-1,-1), 2),
        ('BOTTOMPADDING',(0,0),(-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(prov_tbl)
    story.append(Spacer(1, 1*mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 4. INFOS ÉCOLE (gauche) | INFOS ÉLÈVE (droite)
    # ══════════════════════════════════════════════════════════════════════════
    v_s  = (school.ville    or '') if school else ''
    c_s  = (school.commune  or '') if school else ''
    n_s  = (school.nom      or '') if school else ''
    co_s = (school.code     or '') if school else ''
    p_s  = (school.province or '') if school else ''

    dn = eleve.date_naissance.strftime('%d/%m/%Y') if eleve.date_naissance else '...../...../........'
    nom_complet = f"{eleve.nom} {eleve.postnom} {eleve.prenom}"

    # Cases N° PERM
    perm_chars = list(eleve.matricule or '')[:12]
    while len(perm_chars) < 12:
        perm_chars.append('')
    perm_cases = [Paragraph(f"<b>{c}</b>", ctr_b) for c in perm_chars]
    perm_case_w = (avail_w/2 - 2.5*cm) / 12

    ecole_cell = Paragraph(
        f"<b>VILLE</b> &nbsp;&nbsp;&nbsp; : {v_s}<br/>"
        f"<b>COMMUNE</b> : {c_s}<br/>"
        f"<b>ÉCOLE</b> &nbsp;&nbsp;&nbsp; : {n_s}<br/>"
        f"<b>CODE</b> &nbsp;&nbsp;&nbsp;&nbsp; : {co_s}",
        small
    )

    eleve_perm_tbl = Table(
        [[Paragraph('<b>N° PERM. :</b>', bold)] + perm_cases],
        colWidths=[2.5*cm] + [perm_case_w]*12
    )
    eleve_perm_tbl.setStyle(TableStyle([
        ('GRID',         (1, 0), (-1, -1), 0.5, BLACK),
        ('FONTSIZE',     (0, 0), (-1, -1), 6),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',        (1, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING',   (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 1),
    ]))

    eleve_cell = [
        Paragraph(
            f"<b>ÉLÈVE :</b> {nom_complet} &nbsp;&nbsp;&nbsp; <b>SEXE :</b> {eleve.get_sexe_display()}<br/>"
            f"<b>NÉ(E) À :</b> {eleve.lieu_naissance or ''}............. <b>LE</b> {dn}<br/>"
            f"<b>CLASSE :</b> {modele.classe}",
            small
        ),
        eleve_perm_tbl,
    ]

    # Assembler les deux colonnes
    info_data = [[ecole_cell, eleve_cell]]
    info_tbl  = Table(info_data, colWidths=[avail_w/2, avail_w/2])
    info_tbl.setStyle(TableStyle([
        ('BOX',         (0, 0), (-1, -1), 0.8, BLACK),
        ('LINEBEFORE',  (1, 0), (1, 0),   0.5, BLACK),
        ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',  (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',(0,0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 1*mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 5. TITRE DU BULLETIN
    # ══════════════════════════════════════════════════════════════════════════
    annee_str   = str(modele.annee_scolaire)
    section_nom = (modele.classe.section.nom if modele.classe and hasattr(modele.classe, 'section') and modele.classe.section else 'SECONDAIRE').upper()
    titre_txt = (
        f"BULLETIN DE LA 1<super>ère</super> ET 2<super>ème</super> ANNEE {section_nom}"
        f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ANNEE SCOLAIRE {annee_str}"
    )
    titre_tbl = Table([[Paragraph(titre_txt, titre)]], colWidths=[avail_w])
    titre_tbl.setStyle(TableStyle([
        ('BOX',         (0,0), (-1,-1), 0.8, BLACK),
        ('TOPPADDING',  (0,0), (-1,-1), 3),
        ('BOTTOMPADDING',(0,0),(-1,-1), 3),
        ('BACKGROUND',  (0,0), (-1,-1), GREY_HDR),
    ]))
    story.append(titre_tbl)
    story.append(Spacer(1, 1*mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 6. TABLEAU DES NOTES
    # ══════════════════════════════════════════════════════════════════════════
    # Proportions colonnes : Branches | 1P | 2P | EXAM | TOT | 3P | 4P | EXAM | TOT | TG | % | SIGN.
    COL_RATIOS = [.22, .07, .07, .07, .07, .07, .07, .07, .07, .07, .065, .065]
    COL_W = [avail_w * r for r in COL_RATIOS]

    def _h(txt):  return Paragraph(txt, ctr_b)
    def _c(txt):  return Paragraph(txt, ctr)
    def _b(txt):  return Paragraph(txt, bold)
    def _bl(txt): return Paragraph(txt, small)

    # 3 lignes d'en-têtes fusionnées
    header_rows = [
        [_h('BRANCHES'),
         _h('PREMIER SEMESTRE'), '', '', '',
         _h('SECOND SEMESTRE'),  '', '', '',
         _h('T.G.'),
         _h('EXAMEN DE<br/>REPÊCHAGE'), ''],
        ['',
         _h('TR. JOURNAL.'), '', _h('EXAM'), _h('TOT.'),
         _h('TR. JOURNAL.'), '', _h('EXAM'), _h('TOT.'),
         '', _h('%'), _h('SIGN.<br/>PROF')],
        ['',
         _h('1<super>ère</super> P'), _h('2<super>ème</super> P'), '', '',
         _h('3<super>ème</super> P'), _h('4<super>ème</super> P'), '', '',
         '', '', ''],
    ]

    tbl_data   = list(header_rows)
    row_styles = []
    span_cmds  = []
    current_row = 3

    # Regrouper par maxima
    groups = {}
    for row in matieres_data:
        mx = row['matiere'].maxima
        groups.setdefault(mx, []).append(row)

    for mx in sorted(groups.keys()):
        mx2, mx4, mx8 = mx*2, mx*4, mx*8
        # Ligne MAXIMA
        tbl_data.append([
            _b('MAXIMA'),
            _c(str(mx)), _c(str(mx)), _c(str(mx2)), _c(str(mx4)),
            _c(str(mx)), _c(str(mx)), _c(str(mx2)), _c(str(mx4)),
            _c(str(mx8)), '', '',
        ])
        row_styles.append(('BACKGROUND', (0, current_row), (-1, current_row), GREY_MAX))
        row_styles.append(('FONTNAME',   (0, current_row), (-1, current_row), 'Helvetica-Bold'))
        current_row += 1

        for row in groups[mx]:
            tg_val  = row['tg'] or Decimal('0')
            pct_row = round(float(tg_val) / float(mx*8) * 100, 0) if mx*8 > 0 else ''
            pct_str = f"{int(pct_row)}%" if pct_row != '' else ''
            tbl_data.append([
                _bl(row['matiere'].nom),
                _c(_note_str(row['n1p'])),
                _c(_note_str(row['n2p'])),
                _c(_note_str(row['nexam1'])),
                _c(_note_str(row['tot_s1'])),
                _c(_note_str(row['n3p'])),
                _c(_note_str(row['n4p'])),
                _c(_note_str(row['nexam2'])),
                _c(_note_str(row['tot_s2'])),
                Paragraph(f"<b>{_note_str(tg_val)}</b>", ctr_b),
                _c(_note_str(row['repechage'])),
                '',
            ])
            current_row += 1

    # ── Lignes MAXIMA GÉNÉRAUX ──
    tbl_data.append([_b('MAXIMA GÉNÉRAUX'), '', '', '', '', '', '', '', '', _c(str(int(total_max))), '', ''])
    row_styles.append(('BACKGROUND', (0, current_row), (-1, current_row), GREY_MAX))
    row_styles.append(('FONTNAME',   (0, current_row), (-1, current_row), 'Helvetica-Bold'))
    span_cmds.append(('SPAN', (0, current_row), (8, current_row)))
    span_cmds.append(('SPAN', (10, current_row), (11, current_row)))
    current_row += 1

    # ── Totaux par période + semestriels + TG ─────────────────────────────────
    tot_row = current_row
    tbl_data.append([
        _b('TOTAUX'),
        _c(_note_str(pp['1P']['total'])),
        _c(_note_str(pp['2P']['total'])),
        _c(_note_str(pp['EXAM1']['total'])),
        Paragraph(f"<b>{_note_str(total_s1)}</b>", ctr_b),
        _c(_note_str(pp['3P']['total'])),
        _c(_note_str(pp['4P']['total'])),
        _c(_note_str(pp['EXAM2']['total'])),
        Paragraph(f"<b>{_note_str(total_s2)}</b>", ctr_b),
        Paragraph(f"<b>{_note_str(total_obtenu)}</b>", ctr_b),
        '', '',
    ])
    current_row += 1

    # ── Pourcentage par période + semestriels + annuel ────────────────────────
    pct_row = current_row
    tbl_data.append([
        _b('POURCENTAGE'),
        _c(_pct(pp['1P']['total'],    max_p)),
        _c(_pct(pp['2P']['total'],    max_p)),
        _c(_pct(pp['EXAM1']['total'], max_e)),
        _c(f"{pct_s1}%"),
        _c(_pct(pp['3P']['total'],    max_p)),
        _c(_pct(pp['4P']['total'],    max_p)),
        _c(_pct(pp['EXAM2']['total'], max_e)),
        _c(f"{pct_s2}%"),
        Paragraph(f"<b>{pct}%</b>", ctr_b),
        '', '',
    ])
    current_row += 1

    # ── Mention ───────────────────────────────────────────────────────────────
    mention_row = current_row
    tbl_data.append([
        _b('MENTION'), '', '', '', '', '', '', '', '',
        Paragraph(f"<b>{mention}</b>", ctr_b),
        '', '',
    ])
    current_row += 1

    # ── Place/Rang par période + semestriels + annuel ─────────────────────────
    place_row = current_row
    tbl_data.append([
        _b('PLACE/NBRE ÉLÈVES'),
        _c(f"{pp['1P']['rang']}/{nb_eleves}"),
        _c(f"{pp['2P']['rang']}/{nb_eleves}"),
        _c(f"{pp['EXAM1']['rang']}/{nb_eleves}"),
        _c(f"{rang_s1}/{nb_eleves}"),
        _c(f"{pp['3P']['rang']}/{nb_eleves}"),
        _c(f"{pp['4P']['rang']}/{nb_eleves}"),
        _c(f"{pp['EXAM2']['rang']}/{nb_eleves}"),
        _c(f"{rang_s2}/{nb_eleves}"),
        Paragraph(f"<b>{classement}/{nb_eleves}</b>", ctr_b),
        '', '',
    ])
    current_row += 1

    # ── Application / Conduite (cases grises) ──
    for label in ['APPLICATION', 'CONDUITE']:
        tbl_data.append([_b(label)] + [''] * 11)
        row_styles.append(('BACKGROUND', (1, current_row), (8, current_row), GREY_BG))
        span_cmds.append(('SPAN', (0, current_row), (8, current_row)))
        span_cmds.append(('SPAN', (9, current_row), (11, current_row)))
        current_row += 1

    # ── Signature du responsable ──
    tbl_data.append([_b("SIGN. DU RESPONSABLE")] + [''] * 11)
    span_cmds.append(('SPAN', (0, current_row), (11, current_row)))
    current_row += 1

    # ── Assemblage tableau ──
    note_tbl = Table(tbl_data, colWidths=COL_W, repeatRows=3)

    base_style = [
        # Fond en-têtes
        ('BACKGROUND', (0, 0), (-1, 2), GREY_HDR),
        ('FONTNAME',   (0, 0), (-1, 2), 'Helvetica-Bold'),
        # Dimensions globales
        ('FONTSIZE',   (0, 0), (-1, -1), 6.5),
        ('LEADING',    (0, 0), (-1, -1), 8),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',      (0, 3), (0, -1),  'LEFT'),
        # Fusions en-têtes (3 niveaux)
        ('SPAN', (0, 0),  (0, 2)),    # BRANCHES
        ('SPAN', (1, 0),  (4, 0)),    # PREMIER SEMESTRE
        ('SPAN', (5, 0),  (8, 0)),    # SECOND SEMESTRE
        ('SPAN', (9, 0),  (9, 2)),    # TG
        ('SPAN', (10, 0), (11, 0)),   # EXAMEN DE REPÊCHAGE
        ('SPAN', (1, 1),  (2, 1)),    # TR.JOURNAL S1
        ('SPAN', (3, 1),  (3, 2)),    # EXAM S1
        ('SPAN', (4, 1),  (4, 2)),    # TOT S1
        ('SPAN', (5, 1),  (6, 1)),    # TR.JOURNAL S2
        ('SPAN', (7, 1),  (7, 2)),    # EXAM S2
        ('SPAN', (8, 1),  (8, 2)),    # TOT S2
        ('SPAN', (10, 1), (10, 2)),   # % REPÊCHAGE
        ('SPAN', (11, 1), (11, 2)),   # SIGN.PROF
        # Grille
        ('GRID',      (0, 0), (-1, -1), 0.3, colors.grey),
        ('BOX',       (0, 0), (-1, -1), 0.8, BLACK),
        ('LINEABOVE', (0, 3), (-1, 3),  0.8, BLACK),
        # Padding
        ('TOPPADDING',    (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
        ('LEFTPADDING',   (0, 3), (0, -1),  3),
    ]

    # ── Fusions lignes de bilan ─────────────────────────────────────────────────
    # TOTAUX / POURCENTAGE / PLACE : colonne repêchage fusionnée (vide)
    for row in (tot_row, pct_row, place_row):
        span_cmds.append(('SPAN', (10, row), (11, row)))
    # MENTION : label sur toute la largeur (0-8)
    span_cmds.append(('SPAN', (0, mention_row), (8,  mention_row)))
    span_cmds.append(('SPAN', (10, mention_row), (11, mention_row)))

    note_tbl.setStyle(TableStyle(base_style + row_styles + span_cmds))
    story.append(note_tbl)
    story.append(Spacer(1, 3*mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 7. PIED DE PAGE LÉGAL
    # ══════════════════════════════════════════════════════════════════════════
    footer_lines = [
        "- L'élève ne pourra passer dans la classe supérieure s'il n'a subi avec succès un examen de repêchage en..................................(1)",
        "- L'élève passe dans la classe supérieure (1)",
        "- L'élève double sa classe (1)",
        "- L'élève a échoué et est à réorienter vers.................................(1)",
    ]
    for line in footer_lines:
        story.append(Paragraph(line, tiny))
    story.append(Spacer(1, 5*mm))

    # Signatures
    ville_s = school.ville if school else '...............'
    sigs_tbl = Table([[
        Paragraph("Signature de l'élève", small),
        Paragraph("Sceau de l'école", small),
        Paragraph(
            f"Fait à {ville_s}, le ........./.........../.............<br/>"
            "<b>Le Chef d'Établissement</b><br/>Sceau de l'école",
            small
        ),
    ]], colWidths=[avail_w/3]*3)
    sigs_tbl.setStyle(TableStyle([
        ('ALIGN',  (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(sigs_tbl)
    story.append(Spacer(1, 4*mm))

    # Note de bas de page
    story.append(Paragraph(
        "(1) Biffer la mention inutile &nbsp;&nbsp;&nbsp; "
        "<i>Note importante : Le bulletin est sans valeur s'il est raturé ou surchargé</i>",
        tiny
    ))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("IGE/P.S/005", right))

    # ── Génération ──
    doc.build(story)
    buf.seek(0)
    filename = f"bulletin_{eleve.matricule}_{modele.annee_scolaire}.pdf"
    resp = HttpResponse(buf, content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename="{filename}"'
    return resp


@login_required
def bulletin_eleve_pdf(request, pk, eleve_pk):
    """Vue back-office : génère le PDF du bulletin d'un élève (préfet uniquement)."""
    modele = get_object_or_404(ModeleBulletin, pk=pk)
    if request.user.is_enseignant():
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Accès réservé au Préfet.")
    eleve  = get_object_or_404(Student, pk=eleve_pk)
    return build_bulletin_pdf_response(modele, eleve)
