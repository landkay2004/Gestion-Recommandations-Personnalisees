"""
Script de données de test pour SGN RDC
Lance avec: python manage.py shell -c "exec(open('seed_data.py', encoding='utf-8').read())"
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_app.settings')

from accounts.models import CustomUser
from students.models import Student
from teachers.models import Teacher
from classes.models import AnneeScolaire, Section, Classe
from subjects.models import Matiere, MatiereClasse
from bulletin.models import ModeleBulletin, ModeleBulletinMatiere
from grades.models import Note
from school_settings.models import SchoolInfo
from decimal import Decimal
import datetime

print("=== Démarrage du seeding ===")

# ─── 1. INFOS DE L'ÉCOLE ───────────────────────────────────────────────────────
info, _ = SchoolInfo.objects.get_or_create(pk=1, defaults={
    'nom': 'Institut Technique Industriel KINSHASA',
    'province': 'Kinshasa',
    'ville': 'Kinshasa',
    'commune': 'Kintambo',
    'code': 'ITI/KIN/001',
})
print(f"  École: {info.nom}")

# ─── 2. ANNÉE SCOLAIRE ─────────────────────────────────────────────────────────
annee, _ = AnneeScolaire.objects.get_or_create(annee='2024-2025', defaults={'active': True})
print(f"  Année: {annee.annee}")

# ─── 3. SECTIONS ───────────────────────────────────────────────────────────────
sec_sc, _ = Section.objects.get_or_create(nom='Sciences')
sec_lit, _ = Section.objects.get_or_create(nom='Littéraire')
sec_comm, _ = Section.objects.get_or_create(nom='Commerciale')
print("  Sections créées: Sciences, Littéraire, Commerciale")

# ─── 4. CLASSES ────────────────────────────────────────────────────────────────
classes_data = [
    ('4ème Sciences', sec_sc),
    ('5ème Sciences', sec_sc),
    ('6ème Sciences', sec_sc),
    ('4ème Littéraire', sec_lit),
    ('5ème Littéraire', sec_lit),
    ('4ème Commerciale', sec_comm),
]
classes = {}
for nom, sec in classes_data:
    cl, _ = Classe.objects.get_or_create(nom=nom, section=sec, annee_scolaire=annee)
    classes[nom] = cl
print(f"  {len(classes)} classes créées")

# ─── 5. ENSEIGNANTS ────────────────────────────────────────────────────────────
enseignants_data = [
    ('prof_math',    'ens123', 'Mutombo',  'Jean-Pierre', '+243810000001'),
    ('prof_fr',      'ens123', 'Kabila',   'Marie-Claire','+243810000002'),
    ('prof_bio',     'ens123', 'Lukusa',   'David',       '+243810000003'),
    ('prof_chimie',  'ens123', 'Nzuzi',    'Espoir',      '+243810000004'),
    ('prof_hist',    'ens123', 'Mbemba',   'Sylvie',      '+243810000005'),
]
teachers = {}
for username, pwd, last, first, tel in enseignants_data:
    email = f'{username}@ecole.cd'
    u, created = CustomUser.objects.get_or_create(username=username, defaults={
        'first_name': first, 'last_name': last, 'role': 'enseignant', 'email': email
    })
    if created:
        u.set_password(pwd)
        u.save()
    elif not u.email:
        u.email = email
        u.save()
    t, _ = Teacher.objects.get_or_create(user=u, defaults={'telephone': tel})
    teachers[username] = t
print(f"  {len(teachers)} enseignants créés (mot de passe: ens123)")

# ─── 5bis. PRÉFET & ENSEIGNANT TEST ────────────────────────────────────────────
prefet, created = CustomUser.objects.get_or_create(username='prefet', defaults={
    'first_name': 'Le', 'last_name': 'Préfet',
    'role': 'prefet', 'email': 'prefet@ecole.cd',
    'is_staff': True, 'is_superuser': True,
})
if created:
    prefet.set_password('prefet2024')
    prefet.save()
elif not prefet.email:
    prefet.email = 'prefet@ecole.cd'
    prefet.is_staff = True
    prefet.is_superuser = True
    prefet.save()

ens_test, created = CustomUser.objects.get_or_create(username='enseignant1', defaults={
    'first_name': 'Enseignant', 'last_name': 'Test',
    'role': 'enseignant', 'email': 'enseignant1@ecole.cd',
})
if created:
    ens_test.set_password('ens2024')
    ens_test.save()
elif not ens_test.email:
    ens_test.email = 'enseignant1@ecole.cd'
    ens_test.save()

print(f"  Comptes préfet et enseignant test créés/vérifiés")

# ─── 6. MATIÈRES ───────────────────────────────────────────────────────────────
matieres_data = [
    ('Mathématiques',       60),
    ('Français',            60),
    ('Biologie',            60),
    ('Chimie',              60),
    ('Physique',            60),
    ('Histoire-Géographie', 30),
    ('Éducation Civique',   30),
    ('Anglais',             30),
    ('Éducation Physique',  20),
    ('Religion',            20),
]
matieres = {}
for nom, maxima in matieres_data:
    m, _ = Matiere.objects.get_or_create(nom=nom, defaults={'maxima': maxima})
    matieres[nom] = m
print(f"  {len(matieres)} matières créées")

# ─── 7. AFFECTATIONS MATIÈRES → CLASSES ────────────────────────────────────────
affectations = [
    # 4ème Sciences
    (classes['4ème Sciences'], matieres['Mathématiques'],       teachers['prof_math']),
    (classes['4ème Sciences'], matieres['Français'],            teachers['prof_fr']),
    (classes['4ème Sciences'], matieres['Biologie'],            teachers['prof_bio']),
    (classes['4ème Sciences'], matieres['Chimie'],              teachers['prof_chimie']),
    (classes['4ème Sciences'], matieres['Histoire-Géographie'], teachers['prof_hist']),
    (classes['4ème Sciences'], matieres['Éducation Civique'],   teachers['prof_hist']),
    (classes['4ème Sciences'], matieres['Anglais'],             teachers['prof_fr']),
    (classes['4ème Sciences'], matieres['Éducation Physique'],  None),
    (classes['4ème Sciences'], matieres['Religion'],            None),
    # 5ème Sciences
    (classes['5ème Sciences'], matieres['Mathématiques'],       teachers['prof_math']),
    (classes['5ème Sciences'], matieres['Français'],            teachers['prof_fr']),
    (classes['5ème Sciences'], matieres['Biologie'],            teachers['prof_bio']),
    (classes['5ème Sciences'], matieres['Chimie'],              teachers['prof_chimie']),
    (classes['5ème Sciences'], matieres['Physique'],            teachers['prof_math']),
    (classes['5ème Sciences'], matieres['Anglais'],             teachers['prof_fr']),
    (classes['5ème Sciences'], matieres['Éducation Physique'],  None),
    # 6ème Sciences
    (classes['6ème Sciences'], matieres['Mathématiques'],       teachers['prof_math']),
    (classes['6ème Sciences'], matieres['Français'],            teachers['prof_fr']),
    (classes['6ème Sciences'], matieres['Biologie'],            teachers['prof_bio']),
    (classes['6ème Sciences'], matieres['Chimie'],              teachers['prof_chimie']),
    (classes['6ème Sciences'], matieres['Physique'],            teachers['prof_math']),
    (classes['6ème Sciences'], matieres['Religion'],            None),
    # 4ème Littéraire
    (classes['4ème Littéraire'], matieres['Français'],            teachers['prof_fr']),
    (classes['4ème Littéraire'], matieres['Histoire-Géographie'], teachers['prof_hist']),
    (classes['4ème Littéraire'], matieres['Anglais'],             teachers['prof_fr']),
    (classes['4ème Littéraire'], matieres['Éducation Civique'],   teachers['prof_hist']),
    (classes['4ème Littéraire'], matieres['Mathématiques'],       teachers['prof_math']),
    (classes['4ème Littéraire'], matieres['Religion'],            None),
    # 4ème Commerciale
    (classes['4ème Commerciale'], matieres['Mathématiques'],       teachers['prof_math']),
    (classes['4ème Commerciale'], matieres['Français'],            teachers['prof_fr']),
    (classes['4ème Commerciale'], matieres['Histoire-Géographie'], teachers['prof_hist']),
    (classes['4ème Commerciale'], matieres['Anglais'],             teachers['prof_fr']),
    (classes['4ème Commerciale'], matieres['Éducation Civique'],   teachers['prof_hist']),
]
mc_map = {}
for cl, mat, ens in affectations:
    mc, _ = MatiereClasse.objects.get_or_create(
        matiere=mat, classe=cl,
        defaults={'enseignant': ens}
    )
    mc_map[(cl.pk, mat.pk)] = mc
print(f"  {len(mc_map)} affectations matières-classes créées")

# ─── 8. ÉLÈVES ─────────────────────────────────────────────────────────────────
eleves_data = [
    # 4ème Sciences (8 élèves)
    ('4ème Sciences', 'KASONGO',   'Trésor',   'Bienvenu', 'M', '2008-03-15', 'Kinshasa', 'SC2024001'),
    ('4ème Sciences', 'MWAMBA',    'Grâce',    'Esther',   'F', '2008-07-22', 'Lubumbashi','SC2024002'),
    ('4ème Sciences', 'NTUMBA',    'Patrick',  'Luc',      'M', '2007-11-05', 'Mbuji-Mayi','SC2024003'),
    ('4ème Sciences', 'ILUNGA',    'Patience', 'Marie',    'F', '2008-01-30', 'Kinshasa', 'SC2024004'),
    ('4ème Sciences', 'KALALA',    'Joël',     'Émile',    'M', '2009-05-10', 'Kananga',  'SC2024005'),
    ('4ème Sciences', 'MUKENDI',   'Espoir',   'Rachel',   'F', '2008-09-14', 'Kinshasa', 'SC2024006'),
    ('4ème Sciences', 'TSHISUAKA', 'Aaron',    'Daniel',   'M', '2007-12-20', 'Kinshasa', 'SC2024007'),
    ('4ème Sciences', 'BANZA',     'Joëlle',   'Ruth',     'F', '2008-04-08', 'Matadi',   'SC2024008'),
    # 5ème Sciences (6 élèves)
    ('5ème Sciences', 'KABONGO',   'Emmanuel', 'Paul',     'M', '2007-06-18', 'Kinshasa', 'SC2024009'),
    ('5ème Sciences', 'NKASHAMA',  'Déborah',  'Anne',     'F', '2007-02-25', 'Kisangani','SC2024010'),
    ('5ème Sciences', 'MULUMBA',   'Samuel',   'Théo',     'M', '2006-10-12', 'Kinshasa', 'SC2024011'),
    ('5ème Sciences', 'KAYEMBE',   'Gloire',   'Élise',    'F', '2007-08-03', 'Lubumbashi','SC2024012'),
    ('5ème Sciences', 'LUFUNGULA', 'Christophe','Marc',    'M', '2007-01-27', 'Kinshasa', 'SC2024013'),
    ('5ème Sciences', 'KAPEND',    'Sandrine', 'Lydie',    'F', '2006-11-09', 'Mbuji-Mayi','SC2024014'),
    # 6ème Sciences (5 élèves)
    ('6ème Sciences', 'MBUYI',     'Bienvenu', 'Jonas',    'M', '2005-03-22', 'Kinshasa', 'SC2024015'),
    ('6ème Sciences', 'KYUNGU',    'Aimée',    'Claire',   'F', '2006-07-14', 'Lubumbashi','SC2024016'),
    ('6ème Sciences', 'MUTEBA',    'Didier',   'Pierre',   'M', '2005-09-30', 'Kinshasa', 'SC2024017'),
    ('6ème Sciences', 'LUPEMBA',   'Agnès',    'Noëlle',   'F', '2005-12-05', 'Matadi',   'SC2024018'),
    ('6ème Sciences', 'TSHIBANGU', 'Cédric',   'Levi',     'M', '2006-04-17', 'Kinshasa', 'SC2024019'),
    # 4ème Littéraire (5 élèves)
    ('4ème Littéraire','NGANDU',   'Béatrice', 'Joie',     'F', '2008-06-11', 'Kinshasa', 'LT2024001'),
    ('4ème Littéraire','KALONJI',  'Héritier', 'Abel',     'M', '2008-02-19', 'Kananga',  'LT2024002'),
    ('4ème Littéraire','MUJINGA',  'Clarisse', 'Ève',      'F', '2008-08-26', 'Kinshasa', 'LT2024003'),
    ('4ème Littéraire','MBAYA',    'Josué',    'David',    'M', '2007-10-07', 'Mbuji-Mayi','LT2024004'),
    ('4ème Littéraire','KAZADI',   'Princesse','Miriam',   'F', '2008-05-23', 'Kinshasa', 'LT2024005'),
    # 4ème Commerciale (4 élèves)
    ('4ème Commerciale','KABILA',  'Merveille','Jolie',    'F', '2008-03-01', 'Kinshasa', 'CM2024001'),
    ('4ème Commerciale','NGOYI',   'Israël',   'Nathan',   'M', '2008-09-20', 'Kinshasa', 'CM2024002'),
    ('4ème Commerciale','TSHIMBA', 'Gloire',   'Hanna',    'F', '2009-01-14', 'Lubumbashi','CM2024003'),
    ('4ème Commerciale','MUSAU',   'Aristote', 'Caleb',    'M', '2008-07-08', 'Kinshasa', 'CM2024004'),
]

eleves = {}
for row in eleves_data:
    cl_nom, nom, prenom, pren2, sexe, ddn, lieu, mat = row
    s, _ = Student.objects.get_or_create(matricule=mat, defaults={
        'nom': nom,
        'postnom': prenom,
        'prenom': pren2,
        'sexe': sexe,
        'date_naissance': datetime.date.fromisoformat(ddn),
        'lieu_naissance': lieu,
        'date_inscription': datetime.date(2024, 9, 2),
        'adresse': f'Commune de {lieu}',
        'nom_parent': f'Parent de {nom}',
        'telephone': '',
        'classe': classes[cl_nom],
    })
    eleves[mat] = s
print(f"  {len(eleves)} élèves créés")

# ─── 9. MODÈLES DE BULLETINS ───────────────────────────────────────────────────
bulletins = {}
for cl_nom, cl_obj in classes.items():
    mb, _ = ModeleBulletin.objects.get_or_create(
        classe=cl_obj, annee_scolaire=annee,
        defaults={'publie': True}
    )
    bulletins[cl_nom] = mb
    # Ajouter les matières affectées au bulletin
    mcs = MatiereClasse.objects.filter(classe=cl_obj)
    for ordre, mc in enumerate(mcs, start=1):
        ModeleBulletinMatiere.objects.get_or_create(
            modele=mb, matiere=mc.matiere,
            defaults={'ordre': ordre}
        )
print(f"  {len(bulletins)} modèles de bulletins créés")

# ─── 10. NOTES ─────────────────────────────────────────────────────────────────
import random
random.seed(42)

PERIODES = ['1P', '2P', 'EXAM1', '3P', '4P', 'EXAM2']

def gen_note(maxima, bon=False):
    """Génère une note réaliste selon le maxima."""
    if maxima == 60:
        if bon:
            return round(random.uniform(40, 57), 1)
        return round(random.uniform(25, 55), 1)
    elif maxima == 30:
        if bon:
            return round(random.uniform(20, 29), 1)
        return round(random.uniform(12, 28), 1)
    else:  # 20
        if bon:
            return round(random.uniform(13, 19), 1)
        return round(random.uniform(8, 18), 1)

notes_created = 0
for mat_code, eleve in eleves.items():
    cl = eleve.classe
    # Récupérer les MatiereClasse de la classe de cet élève
    mcs = MatiereClasse.objects.filter(classe=cl)
    bon_eleve = random.random() > 0.4  # 60% bons élèves
    for mc in mcs:
        maxima = mc.matiere.maxima
        for periode in PERIODES:
            valeur = gen_note(maxima, bon=bon_eleve)
            # Diviser par 2 pour EXAM (période d'examen = moitié du maxima)
            if 'EXAM' in periode:
                valeur = round(valeur / 2, 1)
            Note.objects.get_or_create(
                eleve=eleve,
                matiere_classe=mc,
                periode=periode,
                defaults={'valeur': Decimal(str(valeur))}
            )
            notes_created += 1

print(f"  {notes_created} notes créées")
print("\n=== Seeding terminé avec succès ! ===")
print("\nComptes de connexion :")
print("  prefet@ecole.cd      / prefet2024  (Préfet - accès complet)")
print("  enseignant1@ecole.cd / ens2024     (Enseignant test)")
print("  prof_math@ecole.cd   / ens123      (Prof Mathématiques/Physique)")
print("  prof_fr@ecole.cd     / ens123      (Prof Français/Anglais)")
print("  prof_bio@ecole.cd    / ens123      (Prof Biologie)")
print("  prof_chimie@ecole.cd / ens123      (Prof Chimie)")
print("  prof_hist@ecole.cd   / ens123      (Prof Histoire-Géo/Éd. Civique)")