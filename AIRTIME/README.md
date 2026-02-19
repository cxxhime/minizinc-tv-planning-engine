# 📺 Optimiseur de Grille TV

Outil d'optimisation automatique d'une grille de programmes télévisés sur une semaine,
construit avec **Python**, **MiniZinc** (programmation par contraintes) et **Streamlit** (interface web).

---

## Table des matières

1. [Ce que fait le projet](#ce-que-fait-le-projet)
2. [Architecture des fichiers](#architecture-des-fichiers)
3. [Prérequis et installation](#prérequis-et-installation)
4. [Lancer l'application](#lancer-lapplication)
5. [Pipeline de résolution (solver.py)](#pipeline-de-résolution-solverpy)
6. [Le modèle de contraintes (model.mzn)](#le-modèle-de-contraintes-modelmzn)
7. [Le catalogue de programmes (programs.json)](#le-catalogue-de-programmes-programsjson)
8. [L'interface web (app.py)](#linterface-web-apppy)
9. [Concepts clés expliqués](#concepts-clés-expliqués)
10. [Modifier le projet](#modifier-le-projet)

---

## Ce que fait le projet

À partir d'un catalogue de 200 programmes TV (films, séries, documentaires, émissions,
journaux télévisés, météos, sport), l'optimiseur détermine automatiquement **quels programmes
diffuser chaque jour de la semaine** pour :

- **Maximiser le bénéfice net** (revenus publicitaires − coûts d'acquisition)
- **Remplir au maximum la grille** (≥ 34 créneaux de 30 min par jour = 17h de diffusion)
- **Respecter le budget hebdomadaire** (5 000 000 € répartis sur 7 jours)
- **Garantir la diversité éditoriale** (au moins 1 Film, 1 Série, 1 Documentaire, 1 Émission,
  1 Sport par jour)
- **Diffuser les JT obligatoires** (Le 13 Heures à 13:00, Le 20 Heures à 20:00, tous les jours)
- **Respecter les droits de diffusion** (chaque programme passe au maximum 1 fois par semaine,
  sauf JT et bouche-trous de 30 min réutilisables)

---

## Architecture des fichiers

```
airtime_simple/
│
├── data/
│   └── programs.json      ← Catalogue de 200 programmes
│
├── model.mzn              ← Modèle de contraintes MiniZinc (règles + objectif)
├── solver.py              ← Pipeline Python : chargement → résolution → export
├── app.py                 ← Interface web Streamlit
├── requirements.txt       ← Dépendances Python
├── schedule.json          ← Planning généré (produit par le solveur)
└── README.md              ← Ce fichier
```

---

## Prérequis et installation

### 1. Installer MiniZinc

MiniZinc est le moteur de programmation par contraintes utilisé pour résoudre le problème.
Le solveur inclus est **Gecode** (open-source, livré avec MiniZinc).

Télécharger et installer depuis : **https://www.minizinc.org/software.html**

Vérifier l'installation :
```bash
minizinc --version
```

### 2. Installer les dépendances Python

```bash
pip install -r requirements.txt
```

Contenu de `requirements.txt` :
```
streamlit>=1.35
minizinc>=0.9
```

---

## Lancer l'application

### Option A — Interface web (recommandée)

```bash
streamlit run app.py
```

Ouvrir le navigateur à l'adresse : `http://localhost:8501`

Dans la barre latérale :
- Régler la **limite de résolution** (en secondes) — 30 s est suffisant dans la plupart des cas
- Cliquer sur **▶ Générer le Planning**

L'interface affiche ensuite :
- Un bandeau récapitulatif hebdomadaire (coût, revenus pub, bénéfice, rentabilité, audience)
- La rentabilité par jour (vue rapide sur 7 colonnes)
- Le planning journalier détaillé (programmes avec horaires, coûts, barres de rentabilité)
- Un tableau récapitulatif de la semaine

### Option B — Ligne de commande

```bash
python solver.py
```

Le résultat est sauvegardé dans `schedule.json` et un résumé financier est affiché dans le terminal.

---

## Pipeline de résolution (solver.py)

Le fichier `solver.py` orchestre l'ensemble du processus en **5 étapes** :

```
programs.json
     │
     ▼
1. CHARGEMENT   charger_programmes()
     │          Lit le JSON → liste de 200 dicts
     ▼
2. PRÉPARATION  construire_donnees_minizinc()
     │          Préselectionne 140 programmes (3 passes)
     │          Convertit en tableaux d'entiers pour MiniZinc
     ▼
3. RÉSOLUTION   lancer_solveur()
     │          Envoie model.mzn + données à Gecode
     │          Récupère x[jour][programme] ∈ {0,1}
     ▼
4. CONSTRUCTION construire_planning()
     │          Convertit la solution binaire en horaires lisibles
     │          Calcule coûts, revenus pub, bénéfices
     ▼
5. SAUVEGARDE   sauvegarder_planning()
                Écrit schedule.json sur disque
```

### Constantes principales

| Constante | Valeur | Signification |
|---|---|---|
| `DUREE_CRENEAU_MIN` | 30 | 1 créneau = 30 minutes |
| `CRENEAUX_PAR_JOUR` | 36 | 36 × 30 min = 18h (06:00–00:00) |
| `HEURE_DEBUT_DIFFUSION` | 6 | La grille démarre à 06:00 |
| `NB_JOURS` | 7 | Planning sur une semaine |
| `BUDGET_HEBDOMADAIRE` | 5 000 000 € | Budget total de la semaine |
| `CPM` | 7.0 | Coût Pour Mille (€ par 1000 spectateurs par minute de pub) |

### Calcul du revenu publicitaire

```
revenu_pub = (audience / 1000) × CPM × ad_minutes
```

Exemple — Titanic (audience = 4 800 000, ad_minutes = 12, CPM = 7) :
```
(4 800 000 / 1000) × 7 × 12 = 403 200 €
```

### Préselection en 3 passes

Le catalogue contient 200 programmes, mais envoyer toutes les variables à MiniZinc
serait trop lent. On réduit à **140 programmes** via une stratégie en 3 passes :

1. **Passe 1 — JT fixes** : inclure P004 (Le 20 Heures) et P016 (Le 13 Heures) en priorité absolue
2. **Passe 2 — Quota genre** : garantir au moins **7 programmes par genre obligatoire**
   (Film, Série, Documentaire, Émission, Sport) → assure la faisabilité de la contrainte
   "min 1 par genre par jour pendant 7 jours en unicité"
3. **Passe 3 — Score** : compléter jusqu'à 140 avec les meilleurs scores de rentabilité

```
score = (revenu_pub / coût) / pénalité

pénalité = max(1.0, coût / (budget_jour × 0.4))
```

La pénalité défavorise les programmes qui coûteraient plus de 40 % du budget journalier.

### Placement dans la grille horaire

La journée est découpée en **3 fenêtres libres** autour des JT fixes :

```
06:00 ──────────────────── 13:00   Fenêtre Matin      (créneaux 0–13)
13:00 ── Le 13 Heures ─── 13:30   JT 13h fixe        (créneau 14)
13:30 ──────────────────── 20:00   Fenêtre Après-midi (créneaux 15–27)
20:00 ── Le 20 Heures ─── 20:30   JT 20h fixe        (créneaux 28–29)
20:30 ──────────────────── 00:00   Fenêtre Soirée     (créneaux 30–35)
```

Les programmes sélectionnés par MiniZinc sont placés séquentiellement dans chaque fenêtre.
Si un programme est trop long pour l'espace restant d'une fenêtre, il est ignoré.

### Genres (IDs numériques pour MiniZinc)

| ID | Genre | Couleur |
|---|---|---|
| 1 | Journal | 🟠 #FF9500 |
| 2 | Météo | 🔵 #00BFFF |
| 3 | Documentaire | 🟢 #6BCB77 |
| 4 | Film | 🔴 #FF6B6B |
| 5 | Série | 🔵 #4D96FF |
| 6 | Emission | 🟡 #FFD93D |
| 7 | Sport | 🟢 #00C9A7 |

---

## Le modèle de contraintes (model.mzn)

### Variable de décision

```minizinc
array[1..nb_days, 1..nb_programs] of var 0..1: x;
```

`x[d, p] = 1` signifie "le programme `p` est diffusé le jour `d`".
Le solveur détermine simultanément les valeurs de toutes ces variables binaires.

### Contraintes

| ID | Règle | Valeur |
|---|---|---|
| **C1** | Au moins 34 créneaux par jour | `used_slots[d] >= 34` |
| **C2** | Budget journalier plafonné | `coût_jour <= budget / 7` |
| **C3** | Unicité hebdomadaire | Chaque programme (> 1 créneau, hors JT) passe max 1 fois/semaine |
| **C5** | Quota Journal | Max 2 créneaux/jour de Journal hors JT fixes |
| **C5** | Quota autres genres | Max 12 créneaux/jour (~33%) pour Film, Série, Doc, Émission, Sport |
| **C6** | JT obligatoires | Le 13 Heures et Le 20 Heures sont diffusés chaque jour sans exception |
| **C7** | Diversité quotidienne | Min 1 Film + 1 Série + 1 Doc + 1 Émission + 1 Sport par jour |

### Objectif (lexicographique)

```minizinc
solve maximize slots_used_total * 1000000 + profit_total;
```

**Priorité 1** : maximiser le nombre total de créneaux utilisés (remplir la grille)
**Priorité 2** : à remplissage égal, maximiser le profit total

Le facteur × 1 000 000 garantit que remplir un créneau supplémentaire vaut toujours
plus que n'importe quel gain de profit, même si ce programme est déficitaire.

---

## Le catalogue de programmes (programs.json)

### Format d'un programme

```json
{
  "id":               "P015",
  "title":            "Titanic",
  "genre":            "Film",
  "duration_minutes": 195,
  "cost":             160000,
  "base_audience":    4800000,
  "ad_minutes":       12
}
```

| Champ | Type | Description |
|---|---|---|
| `id` | string | Identifiant unique (P001 à P200) |
| `title` | string | Titre du programme |
| `genre` | string | Genre parmi : Journal, Météo, Documentaire, Film, Série, Emission, Sport |
| `duration_minutes` | int | Durée réelle en minutes |
| `cost` | int | Coût de diffusion en € (droits d'acquisition) |
| `base_audience` | int | Nombre de téléspectateurs attendus |
| `ad_minutes` | int | Minutes de publicité vendables dans le programme |

### Distribution du catalogue (200 programmes)

| Genre | Nb programmes | Exemples |
|---|---|---|
| Film | ~41 | Titanic, Avengers Endgame, Intouchables |
| Sport | ~33 | Finale Champions League, Roland Garros, Tour de France |
| Série | ~46 | Game of Thrones, Breaking Bad, Squid Game |
| Emission | ~40 | The Voice, Koh-Lanta, Questions pour un Champion |
| Documentaire | ~26 | Planète Terre, Le Monde de Jamy |
| Journal | 8 | Le 13 Heures (P016), Le 20 Heures (P004) |
| Météo | 5 | Météo du Matin, Météo du Soir |

### Programmes fixes (ancrages de la grille)

- **P016 — Le 13 Heures** : Journal, 30 min, coût 5 800 €, audience 1 020 000
- **P004 — Le 20 Heures** : Journal, 35 min, coût 7 000 €, audience 1 400 000

Ces deux programmes sont toujours inclus dans la préselection et diffusés chaque jour
(contrainte C6 dans model.mzn).

---

## L'interface web (app.py)

L'interface Streamlit se compose de 4 sections :

### 1. Barre latérale
- Curseur **Limite de résolution** (5–3600 s, défaut 30 s)
- Bouton **▶ Générer le Planning**

### 2. Bandeau récapitulatif hebdomadaire
5 métriques : Coût total · Revenus pub · Bénéfice net · Rentabilité · Audience totale
+ Barre de progression du budget utilisé

### 3. Rentabilité par jour
7 mini-cartes (une par jour) affichant le bénéfice net et le ratio de rentabilité.
Vert = rentable, Rouge = déficitaire.

### 4. Planning journalier
Sélecteur de jour (radio horizontal) + cartes détaillées par programme :
- Horaire (HH:MM – HH:MM) avec badge genre coloré
- Barre visuelle de rentabilité (plafonnée à 3×)
- Coût, Revenus pub, Bénéfice pour chaque programme

### 5. Tableau récapitulatif
Tableau Streamlit avec toutes les métriques jour par jour (triable, scrollable).

---

## Concepts clés expliqués

### Programmation par contraintes vs force brute

Avec 140 programmes et 7 jours, l'espace des solutions est de l'ordre de **2^(7×140)**
combinaisons — soit environ 10^295 possibilités. La force brute est impossible.

MiniZinc utilise **Gecode**, un solveur qui explore cet espace par *branch & bound* :
il prune intelligemment les branches impossibles sans les explorer, et améliore
itérativement la solution trouvée jusqu'à la limite de temps.

### Pourquoi un objectif lexicographique ?

Maximiser directement le profit pourrait laisser des créneaux vides si diffuser un programme
supplémentaire est déficitaire. En multipliant les créneaux par 1 000 000, on garantit
que remplir la grille est toujours prioritaire, et le profit n'intervient qu'en départage.

### Pourquoi ≥ 34 créneaux et non = 36 ?

Remplir exactement 36 créneaux avec des programmes de tailles variées (1 à 7 créneaux)
est un problème de **bin packing NP-difficile**. La contrainte stricte = 36 rendrait le
problème infaisable dans la plupart des cas. La borne ≥ 34 garantit des journées
quasi-complètes (≥ 17h) tout en restant toujours faisable.

### CPM (Coût Pour Mille)

Le CPM (7 € dans ce projet) représente le revenu généré pour 1 000 téléspectateurs
par minute de publicité. C'est la valeur réaliste pour la prime time française.
Un programme avec 4 800 000 spectateurs et 12 minutes de pub génère donc :
`(4 800 000 / 1000) × 7 × 12 = 403 200 €` de revenus publicitaires.

---

## Modifier le projet

### Ajouter un programme au catalogue

Éditer `data/programs.json` et ajouter une entrée en respectant le format :
```json
{
  "id": "P201",
  "title": "Mon Nouveau Programme",
  "genre": "Film",
  "duration_minutes": 120,
  "cost": 80000,
  "base_audience": 2000000,
  "ad_minutes": 7
}
```

### Changer le budget

Dans `solver.py` :
```python
BUDGET_HEBDOMADAIRE = 5_000_000   # modifier cette valeur
```

### Changer le CPM (taux de revenus pub)

Dans `solver.py` :
```python
CPM = 7.0   # modifier cette valeur
```

### Modifier une règle éditoriale

Dans `model.mzn`. Par exemple :
- **Exiger 2 films par jour** : trouver la contrainte C7 pour le genre Film et changer `>= 1` en `>= 2`
- **Limiter les séries à 8 créneaux/jour** : trouver la contrainte C5 pour le genre 5 et changer `<= max_slots_genre` par `<= 8`

### Changer les horaires de diffusion

Dans `solver.py` :
```python
CRENEAUX_PAR_JOUR     = 36   # nombre de créneaux (36 × 30 min = 18h)
HEURE_DEBUT_DIFFUSION = 6    # heure de début (6 = 06:00)
```

### Changer le temps de résolution

Dans l'interface Streamlit (curseur) ou par défaut dans `solver.py` :
```python
def solve(..., time_limit: int = 300, ...):
```

### Augmenter la taille du pool MiniZinc

Dans `solver.py` (plus de programmes = plus lent mais plus de diversité) :
```python
programmes = preselectionner_programmes(programmes, nb_max=140)
```
