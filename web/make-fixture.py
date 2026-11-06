"""Generate a fictional, three-page PDF for the real browser/llama.cpp test."""
from pathlib import Path
from reportlab.pdfgen import canvas

root = Path(__file__).resolve().parent
target = root / 'test-results' / 'rag-fiction.pdf'
target.parent.mkdir(exist_ok=True)
c = canvas.Canvas(str(target))
c.setAuthor('Personne fictive - essai technique')
for lines in [
    ['DOSSIER ENTIEREMENT FICTIF - NOVARA',
     'Le projet fictif Azur est pilote par la societe Novara a Lyon.',
     'Le projet commence le 12 mars 2031 et termine le 30 juin 2031.'],
    ['FINANCEMENT DU PROJET AZUR',
     'Le budget total du projet Azur est de 48 275 euros.',
     'Ce montant finance les ordinateurs et la formation des equipes.'],
    ['PROTECTION DES COMPTES',
     'Les salaries doivent activer une authentification a deux facteurs.',
     'Les sauvegardes sont effectuees chaque nuit.'],
]:
    for i, line in enumerate(lines):
        c.drawString(45, 770 - i*24, line)
    c.showPage()
c.save()
print(target)
