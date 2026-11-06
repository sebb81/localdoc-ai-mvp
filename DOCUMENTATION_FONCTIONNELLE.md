# LocalDoc AI — Documentation fonctionnelle

**État décrit : 5 novembre 2026**  
**Public :** utilisateurs, référents métier et personnes chargées de présenter ou de tester l’application.  
**Complément :** [documentation technique](DOCUMENTATION_TECHNIQUE.md).

## 1. À quoi sert LocalDoc AI ?

LocalDoc AI permet d’importer un document sur son PC, de lui poser des questions en français et de consulter les passages utilisés pour produire la réponse.

L’application utilise le RAG, c’est-à-dire la recherche de passages dans un document avant la génération d’une réponse. Le modèle ne reçoit pas systématiquement l’intégralité du fichier : il travaille sur une sélection de passages jugés pertinents.

Exemples de questions :

- « Quel est le budget prévu pour ce projet ? »
- « Dans quelle entreprise ce stage s’est-il déroulé ? »
- « Quelles mesures de sécurité sont mentionnées ? »
- « Quelles sont les dates de début et de fin ? »

La réponse contient des références telles que `[S1]` ou `[S2]`. Les extraits correspondants et les liens vers les pages du document sont affichés sous la réponse.

Le projet est un prototype local. Il permet une utilisation réelle du RAG, mais sa qualité doit être vérifiée sur les documents et les questions de chaque usage.

## 2. Une seule application

Le projet conserve uniquement **LocalDoc RAG WebNN** :

| Élément | Configuration |
|---|---|
| Installation Windows | `installer-webnn.bat` |
| Lancement Windows | `demarrer-webnn.bat` |
| Adresse | <http://127.0.0.1:8766> |
| Recherche | MiniLM dans le navigateur via WebNN, associée à une recherche par mots |
| Réponse | Phi-4 exécuté localement dans llama.cpp |

L'application propose l'import des fichiers, la préparation des passages, les questions, les réponses avec citations et l'ouverture des pages sources.

**L'architecture reste hybride.** WebNN intervient dans la recherche sémantique. Phi-4 génère les réponses dans llama.cpp sur le même PC. La génération n'est pas exécutée dans le navigateur.

Les documents déjà importés sont conservés dans `data/`. Le profil Edge et son cache ont été déplacés dans `web/.edge-profile/` lors du nettoyage du projet.

## 3. Ce qu’il faut pour utiliser l’application

Sur un poste déjà préparé :

- Le dossier complet du projet doit rester accessible en écriture.
- llama.cpp et Phi-4 doivent être préparés par `installer-webnn.bat`.
- La version WebNN doit avoir été préparée avec `installer-webnn.bat`.
- Microsoft Edge doit être installé pour utiliser le lanceur WebNN fourni.

Sur un nouveau poste, suivre la procédure d’installation de la [documentation technique](DOCUMENTATION_TECHNIQUE.md#5-installation-sous-windows). L’installation initiale télécharge des logiciels, des bibliothèques et des modèles. L’utilisation courante s’appuie ensuite sur leurs copies locales.

Une carte graphique compatible peut accélérer Phi‑4. L’application peut aussi fonctionner avec le processeur, avec des délais plus longs. Les performances observées sur le poste de développement ne constituent pas un minimum garanti sur un autre ordinateur.

## 4. Démarrer la version avec recherche WebNN

1. Démarrer avec `demarrer-webnn.bat` : le moteur est chargé automatiquement.
2. Double-cliquer sur **`demarrer-webnn.bat`**, à la racine du projet.
3. Attendre l’ouverture de la fenêtre Edge à l’adresse <http://127.0.0.1:8766>.
4. Vérifier que la zone **Mes documents** apparaît.

Le lanceur utilise un profil Edge propre au projet et active WebNN pour ce lancement. Il conserve les réglages du navigateur habituel.

L’écran principal comprend :

- **Mes documents** : import et sélection d’un fichier.
- **Le document sélectionné** : nom, nombre de pages et de passages.
- **Votre question** : saisie de la demande.
- **Réponse** : texte produit par Phi‑4.
- **Passages utilisés** : références, extraits et pages sources.
- **Options de recherche et informations** : choix du moteur et informations sur le fonctionnement.

## 5. Importer et sélectionner un document

### Formats et limites

| Critère | Comportement actuel |
|---|---|
| Formats acceptés | PDF, TXT et Markdown (`.md`) |
| Taille maximale | 25 Mio, soit 25 × 1 024 × 1 024 octets ; l’écran indique « 25 Mo » |
| Nombre maximal de pages PDF | 600 |
| PDF chiffré | Refusé ; fournir une version déchiffrée autorisée |
| PDF scanné sans texte exploitable | Refusé si aucun passage textuel ne peut être extrait |
| Fichier entièrement vide | Refusé |
| Texte et Markdown | Lecture en UTF‑8 ; une autre source d’encodage peut produire des caractères incorrects |

### Import

1. Dans **Mes documents**, cliquer sur **Choisir un fichier**.
2. Sélectionner le document.
3. Cliquer sur **Importer le document**.
4. Attendre la fin de l’extraction.

Le document est ajouté à la liste puis sélectionné. Son texte est découpé en passages tout en conservant les références de pages.

Un fichier strictement identique à un fichier déjà importé est reconnu comme doublon, même si son nom a changé. L’application réutilise alors le document existant. Un fichier modifié, même légèrement, peut être enregistré comme un autre document.

Pour changer de document, cliquer sur son nom dans la liste. Les questions portent sur **le document sélectionné**, et non sur l’ensemble de la bibliothèque.

## 6. Préparer la recherche

La préparation calcule les représentations numériques des passages, appelées vecteurs. Elles servent à rapprocher une question des passages de sens voisin.

Deux possibilités :

- Cliquer sur **Préparer la recherche WebNN** avant de poser une question.
- Poser directement la question : la préparation est lancée automatiquement si nécessaire.

Pendant cette étape, une progression indique le nombre de passages traités. Les principales actions sont temporairement désactivées pour éviter de changer de document pendant le traitement.

L’index est conservé dans le stockage local de ce profil navigateur. À une ouverture suivante, le message **Index local retrouvé** indique qu’il a pu être réutilisé. L’initialisation du moteur peut toutefois prendre un peu de temps même si les vecteurs sont déjà enregistrés.

Une nouvelle préparation peut être nécessaire après un changement de profil ou de navigateur, un effacement des données du site, une modification du modèle ou un changement du document. Si le stockage du navigateur échoue, l’index reste utilisable dans la fenêtre courante, avec un message explicatif.

## 7. Poser une question et lire la réponse

1. Sélectionner un document.
2. Saisir une question précise dans **Votre question**.
3. Cliquer sur **Poser la question**.
4. Attendre la recherche des passages, puis la rédaction par Phi‑4.

La question doit contenir entre 3 et 1 000 caractères. La version WebNN retire les espaces en début et en fin avant de vérifier la longueur minimale.

Les passages retrouvés apparaissent avant la fin de la génération. La réponse complète s’affiche ensuite ; elle n’est pas affichée progressivement mot par mot dans cette version.

Exemple avec des données entièrement fictives :

> **Question :** Quel est le budget du projet Azur ?  
> **Réponse :** Le budget du projet Azur est de 48 275 euros [S1].

Sous cette réponse, `[S1] · Page 2` permet d’ouvrir le document à la page associée. Le texte source est aussi lisible directement dans l’interface. Pour un TXT ou un Markdown, l’application utilise une seule page logique.

**Une citation permet de contrôler une réponse ; elle ne certifie pas à elle seule que toutes les affirmations sont exactes.** Vérifier le passage cité, en particulier pour les montants, les dates, les noms et les décisions importantes.

Un message peut signaler une réponse vide, l’absence de renvoi explicite aux sources ou une référence détectée qui n’existe pas dans la sélection. Les contrôles automatiques de citations restent limités.

### Bien formuler sa demande

Privilégier une question précise : « Quelles dates sont prévues pour le projet Azur ? » est généralement plus exploitable que « Explique tout ».

Chaque question est traitée indépendamment. Il faut donc reformuler le sujet plutôt que demander « Et son budget ? » en supposant que la question précédente sera mémorisée.

Une demande comme « De qui parle ce document ? » peut identifier son sujet à partir des passages retenus. Elle ne garantit pas une lecture exhaustive de toutes les pages.

## 8. Comprendre les temps affichés

| Indicateur | Signification dans la version WebNN |
|---|---|
| Recherche | Préparation éventuelle de l’index, recherche par mots et recherche sémantique jusqu’à la sélection des passages |
| Réponse | Traitement serveur pour la réponse Phi‑4, pouvant inclure son chargement, la lecture du contexte et la génération |

La première question peut être plus lente : le navigateur initialise son moteur et llama.cpp peut devoir charger Phi‑4.

Phi-4 reste chargé tant que llama-server fonctionne. Le cache de contexte peut accélérer une question répétée.

### Mesures locales observées le 5 novembre 2026

| Situation | Temps de réponse observé |
|---|---:|
| Avant restauration de l’accélération GPU, calcul sur CPU | 50,348 s |
| Premier appel mesuré sur GPU, chargement inclus | 15,387 s |
| Répétition immédiate de la même requête, avec cache | 2,253 s |

Ces mesures concernent le poste équipé d’une RTX 4080 Laptop de 12 Go, avec Phi‑4 et une sélection de six passages. Le temps de 2,253 s correspond à une répétition en cache, pas à une promesse pour toute nouvelle question. Le premier appel GPU comprenait environ 7,1 s de chargement.

Le détail est conservé dans le [rapport local de performance](data/webnn-performance.json), lorsqu’il est présent dans la copie du projet.

## 9. Ouvrir ou supprimer un document

**Ouvrir le document** affiche le fichier original dans un nouvel onglet. Les liens des sources ajoutent la page PDF à ouvrir ; le comportement exact dépend du lecteur du navigateur.

**Supprimer** demande une confirmation, puis retire le fichier original et ses données dans la base locale. Cette opération ne comporte pas de corbeille applicative.

Le cache de vecteurs WebNN n’est pas automatiquement purgé par cette action. Pour effacer également les données conservées par le navigateur, utiliser la gestion des données du site dans le profil Edge dédié. Cette opération peut supprimer les index de tous les documents pour ce site ; ils devront être recalculés.

## 10. Choisir un autre moteur de recherche

Dans **Options de recherche et informations**, les choix proposés sont :

| Choix | Utilisation |
|---|---|
| WebNN · préférence GPU | Choix par défaut pour demander l’accélération de la recherche |
| WebNN · préférence CPU | Demande un contexte WebNN avec préférence processeur |
| WebNN · préférence NPU | Essai sur un matériel compatible ; la réussite ne prouve pas l’utilisation d’un NPU |
| WASM · CPU du navigateur | Exécution dans le navigateur sans demander WebNN |

Le changement de moteur concerne la recherche des passages. Phi‑4 continue à rédiger dans llama.cpp.

Le type de périphérique demandé est une préférence. Le navigateur choisit l’exécution réelle et ONNX Runtime peut répartir les opérations entre WebNN et du calcul CPU. L’application ne remplace pas silencieusement une API WebNN absente par le mode WASM : ce dernier doit être choisi explicitement.

## 11. Résoudre les difficultés courantes

| Symptôme | Première action |
|---|---|
| « WebNN n’est pas activé dans ce navigateur » | Fermer l’onglet concerné et rouvrir avec `demarrer-webnn.bat` ; au besoin, sélectionner explicitement WASM dans les options |
| « llama.cpp indisponible » | Relancer `demarrer-webnn.bat` ; consulter `web/.launcher/llama-error.log` |
| Moteur ou modèle absent | Relancer `installer-webnn.bat` ; vérifier `models/phi4.gguf` |
| Réponse très lente | Séparer le temps de recherche du temps de réponse ; faire vérifier l’utilisation du GPU avec les journaux llama.cpp et `nvidia-smi` |
| Aucun texte lisible détecté | Vérifier si le PDF est un scan ; l’application n’intègre pas d’OCR |
| Une partie du PDF manque | Vérifier les pages sans texte et la qualité de l’extraction ; les tableaux et mises en page complexes peuvent être mal extraits |
| Mauvaise réponse malgré des citations | Lire les extraits et reformuler une question plus précise ; les citations ne suffisent pas à valider le raisonnement |
| Les documents ont disparu de la liste | Vérifier le dossier de projet lancé et le dossier de données configuré ; un effacement du cache du navigateur seul ne supprime normalement pas les originaux du serveur |
| « Lancez d’abord installer-webnn.bat » | Préparer les fichiers du prototype avec ce script avant de relancer |

Fermer la fenêtre Edge ne ferme pas le serveur WebNN lancé en arrière-plan. Pour un arrêt complet ou une mise à jour, suivre la procédure de maintenance de la documentation technique.

## 12. Données locales et limites de confidentialité

Le code applicatif utilise les services de la machine : navigateur, serveur Python, SQLite et llama.cpp. Les modèles et leurs fichiers sont téléchargés lors de l’installation initiale. Le projet n’intègre pas de service d’analyse d’audience ni de CDN pour les fichiers de l’interface compilée.

Cela ne constitue pas une homologation de sécurité. Les documents et les passages sont conservés sur disque sans chiffrement applicatif. Il n’y a ni compte utilisateur, ni cloisonnement par personne, ni contrôle d’accès applicatif. Le navigateur possède également son propre cache de vecteurs. Les politiques du poste, du navigateur et d’llama.cpp restent à vérifier dans un contexte professionnel.

L’application est prévue pour une utilisation locale sur `127.0.0.1`. Un partage réseau ou une exposition sur Internet nécessiterait des protections qui ne sont pas implémentées dans cette version.

## 13. Périmètre actuel

| Disponible | Non implémenté ou non garanti |
|---|---|
| Plusieurs documents dans la bibliothèque | Question croisant plusieurs documents à la fois |
| Questions/réponses sur le document choisi | Mémoire de conversation entre les questions |
| Sources avec extraits et pages | Vérification automatique complète de la vérité des réponses |
| Recherche textuelle et sémantique | OCR des scans, lecture des images ou analyse visuelle des pages |
| Réponses en français demandées au modèle | Pertinence équivalente sur tout type de document français |
| Génération locale avec Phi‑4 | Phi‑4 exécuté via WebNN dans le navigateur |
| Consultation des passages retenus | Résumé exhaustif garanti de toutes les pages |
| Préparation et cache des index | Export métier des réponses ou historique durable des échanges |

Pour une recette fonctionnelle, utiliser des documents dont les réponses attendues sont connues : un montant et sa page, une date, un organisme, puis une information absente. Vérifier séparément la qualité des passages retrouvés et celle de la réponse produite.
