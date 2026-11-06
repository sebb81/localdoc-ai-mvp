# LocalDoc AI — RAG WebNN

Application locale pour importer un PDF/TXT/MD, lui poser des questions en français et consulter les extraits et pages utilisés pour la réponse.

**Une seule version :** recherche dans le navigateur avec MiniLM/WebNN, recherche de mots avec SQLite, puis génération avec **Phi-4 dans llama.cpp**. L'architecture reste hybride ; Phi-4 n'est pas exécuté par WebNN.

## Installer

Prérequis : Windows, Python compatible avec les dépendances, Node.js compatible Vite 7 (20.19+ ou 22.12+) et Microsoft Edge. Le poste testé utilise Python 3.11 et Node 24. Le script installe llama.cpp/CUDA 12.4 pour Windows x64 et GPU NVIDIA.

Depuis la racine du projet :

```powershell
.\installer-webnn.bat
```

Le script installe llama.cpp b12110 et ses bibliothèques CUDA officielles, puis réutilise le GGUF Phi-4 présent dans le stockage Ollama via un lien NTFS (copie si nécessaire). Sans modèle existant, placer un Phi-4 GGUF dans `models/phi4.gguf`. Ollama ne sert plus à exécuter LocalDoc.

Le script prépare Python dans `.venv`, installe les dépendances JavaScript, télécharge MiniLM (environ 91 Mo) et compile l'interface. Les téléchargements initiaux nécessitent Internet. Les modèles restent ensuite locaux.

## Utiliser

Double-cliquer sur **`demarrer-webnn.bat`**. Le lanceur charge automatiquement Phi-4 dans llama.cpp sur `127.0.0.1:8081` avant de démarrer l’application. L'application s'ouvre sur <http://127.0.0.1:8766> dans un profil Edge dédié avec WebNN activé.

1. Importer un document ou sélectionner un document existant.
2. Poser une question ; la première demande prépare automatiquement l'index.
3. Lire la réponse et vérifier les passages cités.

PDF/TXT/MD : 25 Mio maximum ; PDF : 600 pages maximum. Pas d'OCR. Chaque question porte sur le document sélectionné.

## Structure

```text
localdoc/        API FastAPI, extraction, SQLite et client Phi-4/llama.cpp
web/             Interface RAG, worker WebNN, build et lanceur Edge
tests/           Tests Python
data/            Documents et base SQLite conservés
```

Les documents se trouvent dans `data/` (ou `LOCALDOC_DATA_DIR` si configuré). Les vecteurs MiniLM sont conservés dans IndexedDB, dans le profil `web/.edge-profile/`. Les caches et fichiers de modèle générés sont exclus du versionnement.

## Développement et tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q tests
cd web
npm ci
node prepare.mjs
npm run build
```

Démarrage manuel, depuis la racine :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start-llamacpp.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start-llamacpp.ps1
.\.venv\Scripts\python.exe -m uvicorn localdoc.main:app --host 127.0.0.1 --port 8766
```

Le lanceur Windows ajoute l'activation WebNN dans Edge. Un navigateur ouvert sans cette option peut ne pas exposer l'API.

## Documentation

- [Documentation fonctionnelle](DOCUMENTATION_FONCTIONNELLE.md) : utilisation, limites et dépannage.
- [Documentation technique](DOCUMENTATION_TECHNIQUE.md) : architecture, API, installation, maintenance et recette navigateur.

MiniLM est principalement anglophone : la pertinence française doit être vérifiée. Les citations ne certifient pas les affirmations. L'application est un prototype local, sans authentification ni chiffrement applicatif ; ne pas l'exposer sur le réseau sans protections supplémentaires.

## Configuration llama.cpp

- `LOCALDOC_LLAMA_URL` : URL du serveur (défaut `http://127.0.0.1:8081`). Un serveur personnalisé doit être lancé avec `--alias phi4`.
- `LOCALDOC_MODEL_PATH` : chemin du GGUF pour le lanceur (défaut `models/phi4.gguf`).
- `LOCALDOC_GPU_LAYERS` : couches GPU (défaut `99`, `0` pour CPU).

Définir les variables avant le lancement ; aucun `.env` n’est lu automatiquement. Le modèle reste chargé tant que llama-server fonctionne. Journaux : `web/.launcher/llama.log` et `llama-error.log`. Les anciennes preuves Ollama dans `web/evidence/` restent historiques ; elles ne valident pas llama.cpp.
