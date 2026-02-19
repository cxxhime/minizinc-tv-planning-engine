

import json
import math
from collections import Counter
from datetime import date, timedelta

import minizinc  


DUREE_CRENEAU_MIN     = 30         
CRENEAUX_PAR_JOUR     = 36         
HEURE_DEBUT_DIFFUSION = 6          
NB_JOURS              = 7           
BUDGET_HEBDOMADAIRE   = 5_000_000   


CPM = 7.0


IDS_GENRES = {
    "Journal":      1,
    "Météo":        2,
    "Documentaire": 3,
    "Film":         4,
    "Série":        5,
    "Emission":     6,
    "Sport":        7,
}


COULEURS_GENRES = {
    "Journal":      "#FF9500",
    "Météo":        "#00BFFF",
    "Documentaire": "#6BCB77",
    "Film":         "#FF6B6B",
    "Série":        "#4D96FF",
    "Emission":     "#FFD93D",
    "Sport":        "#00C9A7",
}

NOMS_JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


GENRE_COLORS  = COULEURS_GENRES
SLOTS_PER_DAY = CRENEAUX_PAR_JOUR
SLOT_MINUTES  = DUREE_CRENEAU_MIN
WEEKLY_BUDGET = BUDGET_HEBDOMADAIRE




def charger_programmes(chemin: str) -> list[dict]:
    """
    Charge la liste des programmes depuis un fichier JSON.

    Arguments :
        chemin (str) : chemin vers programs.json
                       ex. "data/programs.json"

    Retourne :
        list[dict] : liste de programmes, chaque dict ayant la forme :
            {
              "id"            : "P001",          # identifiant unique
              "title"         : "Le 20 Heures",  # titre affiché
              "genre"         : "Journal",        # voir IDS_GENRES
              "duration_minutes": 35,             # durée réelle en minutes
              "cost"          : 7000,             # coût de diffusion (€)
              "base_audience" : 1400000,          # téléspectateurs attendus
              "ad_minutes"    : 2                 # minutes de pub vendables
            }
    """
    with open(chemin, encoding="utf-8") as f:
        programmes = json.load(f)
    print(f"[chargeur] {len(programmes)} programmes chargés depuis '{chemin}'")
    return programmes


def load_programs(path: str) -> list[dict]:
    """Alias anglais de charger_programmes() — conservé pour app.py."""
    return charger_programmes(path)




def duree_en_creneaux(minutes: int) -> int:
    """
    Convertit une durée en minutes en nombre de créneaux de 30 min.
    On arrondit toujours au supérieur pour ne pas déborder sur le créneau suivant.

    Arguments :
        minutes (int) : durée brute du programme en minutes

    Retourne :
        int : nombre de créneaux occupés (arrondi au supérieur)

    Exemples :
        30 min  → 1 créneau
        35 min  → 2 créneaux  (arrondi car 35 > 30)
        60 min  → 2 créneaux
        90 min  → 3 créneaux
        107 min → 4 créneaux
    """
    return math.ceil(minutes / DUREE_CRENEAU_MIN)


def calculer_revenu_pub(programme: dict) -> int:
    """
    Calcule le revenu publicitaire estimé d'un programme.

    Formule :
        revenu = (audience / 1000) × CPM × ad_minutes

    Explication :
        - audience / 1000  : nombre de "milliers de téléspectateurs"
        - × CPM            : revenu par millier de spectateurs par minute de pub
        - × ad_minutes     : nombre de minutes de publicité vendables dans le programme

    Exemple concret — Titanic (audience=4 800 000, ad_minutes=12, CPM=7) :
        (4 800 000 / 1000) × 7 × 12 = 403 200 €

    Arguments :
        programme (dict) : dict d'un programme avec au moins
                           "base_audience" (int) et "ad_minutes" (int)

    Retourne :
        int : revenu publicitaire arrondi à l'euro près
    """
    audience    = programme["base_audience"]
    minutes_pub = programme.get("ad_minutes", 0)
    revenu      = (audience / 1000.0) * CPM * minutes_pub
    return round(revenu)


def compute_ad_revenue(program: dict) -> int:
    """Alias anglais de calculer_revenu_pub() — conservé pour app.py."""
    return calculer_revenu_pub(program)


def preselectionner_programmes(programmes: list[dict], nb_max: int = 140) -> list[dict]:
    """
    Réduit le catalogue de 200 programmes à nb_max pour limiter la complexité
    de MiniZinc (moins de variables binaires = résolution plus rapide).

    Stratégie en 3 passes :
        1. Inclure en priorité les JT fixes (P004, P016) — toujours diffusés
        2. Garantir au moins 7 programmes par genre obligatoire (Film, Série,
           Documentaire, Emission, Sport) pour que la contrainte C7 (min 1/jour
           pendant 7 jours en unicité) soit faisable
        3. Compléter jusqu'à nb_max avec les meilleurs scores de rentabilité

    Score de rentabilité :
        score = (revenu_pub / coût) / pénalité

        pénalité = max(1.0, coût / (budget_jour × 0.4))
        → Pénalise les programmes qui coûtent plus de 40% du budget journalier
          pour éviter qu'un seul programme dévore tout le budget d'une journée.

    Arguments :
        programmes (list[dict]) : catalogue complet chargé depuis programs.json
        nb_max (int)            : taille maximale du pool envoyé à MiniZinc
                                  (défaut 140, compromis vitesse/diversité)

    Retourne :
        list[dict] : sous-liste de nb_max programmes enrichis d'un champ "_score"
    """
    ids_fixes      = {"P016", "P004"}   
    genres_obliges = {"Film": 7, "Série": 7, "Documentaire": 7, "Emission": 7, "Sport": 7}
    budget_jour    = BUDGET_HEBDOMADAIRE / NB_JOURS  

   
    for p in programmes:
        rev      = (p["base_audience"] / 1000.0) * CPM * p.get("ad_minutes", 0)
        cout     = max(p["cost"], 1)                          
        penalite = max(1.0, p["cost"] / (budget_jour * 0.4)) 
        p["_score"] = (rev / cout) / penalite

 
    selectionnes     = [p for p in programmes if p["id"] in ids_fixes]
    ids_selectionnes = {p["id"] for p in selectionnes}

   
    for genre, minimum in genres_obliges.items():
        candidats = sorted(
            [p for p in programmes if p["genre"] == genre and p["id"] not in ids_selectionnes],
            key=lambda x: x["_score"], reverse=True
        )
        for p in candidats[:minimum]:
            selectionnes.append(p)
            ids_selectionnes.add(p["id"])

    
    reste = sorted(
        [p for p in programmes if p["id"] not in ids_selectionnes],
        key=lambda x: x["_score"], reverse=True
    )
    selectionnes += reste[: nb_max - len(selectionnes)]

    dist = Counter(p["genre"] for p in selectionnes)
    print(f"[préselection] {len(selectionnes)}/{len(programmes)} retenus — " +
          " | ".join(f"{g}:{n}" for g, n in sorted(dist.items())))
    return selectionnes


def construire_donnees_minizinc(programmes: list[dict]) -> tuple[list[dict], dict]:
    """
    Pré-sélectionne les programmes puis construit le dictionnaire de paramètres
    attendu par model.mzn.

    MiniZinc ne reçoit pas des dicts Python : il faut lui passer des tableaux
    d'entiers indexés de 1 à nb_programs. Cette fonction fait la conversion.

    Arguments :
        programmes (list[dict]) : catalogue complet chargé depuis programs.json

    Retourne :
        tuple :
            [0] programmes_filtres (list[dict]) : les 140 programmes retenus.
                 IMPORTANT — les indices de la solution MiniZinc correspondront
                 à cette liste (pas aux 200 programmes originaux).
            [1] donnees (dict) : paramètres pour model.mzn, avec :
                - nb_programs   : nombre de programmes dans le pool
                - nb_days       : 7 (NB_JOURS)
                - budget        : budget hebdomadaire total (€)
                - durations     : tableau des durées en créneaux
                - costs         : tableau des coûts (€)
                - audiences     : tableau des audiences (nb téléspectateurs)
                - genres        : tableau des IDs de genre (entiers 1–7)
                - ad_revenues   : tableau des revenus pub calculés (€)
                - profits       : tableau des bénéfices = revenu - coût (peut être négatif)
                - slots_per_day : 36
                - max_duration  : durée max en créneaux parmi tous les programmes
                - fixed_day     : tableau de 0 (non utilisé, réservé pour extension future)
                - idx_jt13      : position 1-based de "Le 13 Heures" (P016) dans le pool
                - idx_jt20      : position 1-based de "Le 20 Heures" (P004) dans le pool
    """
   
    programmes = preselectionner_programmes(programmes, nb_max=140)
    nb         = len(programmes)

    durees      = [duree_en_creneaux(p["duration_minutes"]) for p in programmes]
    couts       = [p["cost"]                                for p in programmes]
    audiences   = [p["base_audience"]                       for p in programmes]
    genres      = [IDS_GENRES.get(p["genre"], 0)            for p in programmes]
    revenus_pub = [calculer_revenu_pub(p)                   for p in programmes]

   
    benefices = [revenus_pub[i] - couts[i] for i in range(nb)]

    duree_max = max(durees)
    jour_fixe = [0] * nb  

  
    ids_programmes = [p["id"] for p in programmes]
    idx_jt13 = next((i + 1 for i, pid in enumerate(ids_programmes) if pid == "P016"), 1)
    idx_jt20 = next((i + 1 for i, pid in enumerate(ids_programmes) if pid == "P004"), 2)

    donnees = {
        "nb_programs":   nb,
        "nb_days":       NB_JOURS,
        "budget":        BUDGET_HEBDOMADAIRE,
        "durations":     durees,
        "costs":         couts,
        "audiences":     audiences,
        "genres":        genres,
        "ad_revenues":   revenus_pub,
        "profits":       benefices,
        "slots_per_day": CRENEAUX_PAR_JOUR,
        "max_duration":  duree_max,
        "fixed_day":     jour_fixe,
        "idx_jt13":      idx_jt13,
        "idx_jt20":      idx_jt20,
    }
    return programmes, donnees




def lancer_solveur(chemin_modele: str, donnees: dict, limite_secondes: int = 120) -> list | None:
    """
    Envoie le modèle MiniZinc et les données au solveur Gecode et récupère
    la meilleure solution trouvée dans le temps imparti.

    Fonctionnement interne :
        - MiniZinc charge model.mzn (contraintes + objectif)
        - Gecode explore l'espace de 2^(7×140) combinaisons binaires possibles
          via backtracking intelligent (branch & bound)
        - Il retourne la meilleure solution trouvée avant la limite de temps

    Arguments :
        chemin_modele    (str) : chemin vers model.mzn
        donnees          (dict): paramètres produits par construire_donnees_minizinc()
        limite_secondes  (int) : timeout en secondes (défaut 120s)
                                 Gecode retourne la meilleure solution trouvée
                                 à l'expiration, même si non optimale.

    Retourne :
        list ou None :
            - list : tableau 2D x[jour][programme] avec x ∈ {0, 1}
                     x[j][p] = 1 signifie "le programme p est diffusé le jour j"
            - None : aucune solution trouvée (problème infaisable ou timeout trop court)
    """
    print("[solveur] Chargement du modèle MiniZinc …")
    modele   = minizinc.Model(chemin_modele)
    solveur  = minizinc.Solver.lookup("gecode")  
    instance = minizinc.Instance(solveur, modele)

  
    for cle, valeur in donnees.items():
        instance[cle] = valeur

    print(f"[solveur] Résolution en cours … (limite : {limite_secondes}s)")
    resultat = instance.solve(
        timeout=timedelta(seconds=limite_secondes),
        optimisation_level=1, 
        processes=4,          
    )

    if resultat.status in (
        minizinc.result.Status.OPTIMAL_SOLUTION,
        minizinc.result.Status.SATISFIED,
    ):
        print(f"[solveur] ✓ Statut : {resultat.status.name}")
        return resultat["x"]  
    else:
        print(f"[solveur] ✗ Aucune solution. Statut : {resultat.status}")
        return None




def minutes_en_hhmm(total_minutes: int) -> str:
    """
    Convertit un nombre de minutes depuis minuit en chaîne horaire "HH:MM".

    Arguments :
        total_minutes (int) : minutes depuis minuit (ex. 360 = 06:00, 810 = 13:30)

    Retourne :
        str : heure formatée "HH:MM" (ex. "13:30", "20:00")

    Exemples :
        360  → "06:00"   (début de diffusion)
        780  → "13:00"   (JT 13h)
        1200 → "20:00"   (JT 20h)
        1440 → "00:00"   (minuit)
    """
    h = (total_minutes // 60) % 24
    m = total_minutes % 60
    return f"{h:02d}:{m:02d}"


def construire_planning(
    solution: list,
    programmes: list[dict],
    donnees: dict,
    debut_semaine: date,
) -> dict:
    """
    Convertit la solution binaire brute de MiniZinc en un planning lisible
    avec horaires, coûts et revenus calculés pour chaque programme.

    Logique de placement horaire :
        La grille journalière (06:00–00:00, 36 créneaux) est découpée en
        3 fenêtres autour des JT fixes :

        Fenêtre 1 — Matin     : créneaux  0–13  (06:00–13:00)  → programmes libres
                    JT 13h    : créneaux 14–14  (13:00–13:30)  → forcé
        Fenêtre 2 — Après-midi: créneaux 15–27  (13:30–20:00)  → programmes libres
                    JT 20h    : créneaux 28–29  (20:00–20:30)  → forcé (35min = 2 créneaux)
        Fenêtre 3 — Soirée    : créneaux 30–35  (20:30–00:00)  → programmes libres

        Les programmes libres sont placés séquentiellement dans chaque fenêtre.
        Si un programme est trop long pour la fenêtre restante, il est ignoré
        (ne sera pas affiché ce jour-là même s'il a été sélectionné).

    Arguments :
        solution       (list)      : tableau 2D x[jour][prog] ∈ {0,1} retourné par MiniZinc
                                     Les indices correspondent à la liste filtrée (140 progs),
                                     PAS au catalogue original de 200 programmes.
        programmes     (list[dict]): les 140 programmes filtrés (même ordre que solution)
        donnees        (dict)      : paramètres produits par construire_donnees_minizinc()
                                     utilisés pour récupérer durations et ad_revenues
        debut_semaine  (date)      : date du lundi de la semaine planifiée

    Retourne :
        dict : planning complet avec la structure :
            {
              "semaine_debut"   : "2026-02-23",
              "jours"           : [ <dict par jour>, ... ],   # 7 entrées
              "total_cout"      : 4200000,   # somme des coûts sur la semaine (€)
              "total_revenu_pub": 5800000,   # somme des revenus pub (€)
              "total_benefice"  : 1600000,   # revenu - coût global (€)
              "total_audience"  : 42000000,  # somme des audiences sur la semaine
              "rentabilite"     : 1.38,      # ratio revenu_pub / coût global
            }

            Chaque entrée de "jours" contient :
            {
              "name"            : "Lundi",
              "date"            : "2026-02-23",
              "programs"        : [ <dict par programme>, ... ],
              "total_cost"      : 600000,
              "total_ad_revenue": 830000,
              "total_profit"    : 230000,
              "total_audience"  : 6000000,
              "profitability"   : 1.38,
              "slots_used"      : 35,
            }

            Chaque entrée de "programs" contient :
            {
              "title"        : "Titanic",
              "genre"        : "Film",
              "color"        : "#FF6B6B",
              "start"        : "20:30",
              "end"          : "23:15",
              "slots"        : 6,          # créneaux occupés (durée arrondie)
              "duration"     : 195,        # durée réelle en minutes
              "cost"         : 160000,     # coût de diffusion (€)
              "ad_revenue"   : 403200,     # revenu pub calculé (€)
              "profit"       : 243200,     # ad_revenue - cost (€)
              "profitability": 2.52,       # ratio ad_revenue / cost
              "audience"     : 4800000,
              "ad_minutes"   : 12,
            }
    """
    planning = {
        "semaine_debut":    str(debut_semaine),
        "jours":            [],
        "total_cout":       0,
        "total_revenu_pub": 0,
        "total_benefice":   0,
        "total_audience":   0,
    }

    planning["week_start"]       = planning["semaine_debut"]
    planning["days"]             = planning["jours"]
    planning["total_cost"]       = 0
    planning["total_ad_revenue"] = 0
    planning["total_profit"]     = 0

    durees      = donnees["durations"]
    revenus_pub = donnees["ad_revenues"]

   
    SLOT_JT13 = (13 - HEURE_DEBUT_DIFFUSION) * 2   # = 14 → 13:00
    SLOT_JT20 = (20 - HEURE_DEBUT_DIFFUSION) * 2   # = 28 → 20:00

    id_jt13 = donnees.get("idx_jt13", 1) - 1  
    id_jt20 = donnees.get("idx_jt20", 2) - 1

    def construire_entree(prog: dict, idx_prog: int, slot_debut: int) -> dict:
        """
        Construit le dict d'un programme placé à un slot donné.

        Arguments :
            prog      (dict) : données du programme (title, genre, cost…)
            idx_prog  (int)  : index 0-based dans la liste filtrée
                               → permet de récupérer durees[idx_prog] et revenus_pub[idx_prog]
            slot_debut (int) : créneau de début (0-based, 0 = 06:00)
                               → converti en minutes pour calculer start/end

        Retourne :
            dict : entrée programme complète pour le planning JSON
        """
        creneaux    = durees[idx_prog]
        rev_pub     = revenus_pub[idx_prog]
        cout        = prog["cost"]
       
        min_debut   = HEURE_DEBUT_DIFFUSION * 60 + slot_debut * DUREE_CRENEAU_MIN
        min_fin     = min_debut + creneaux * DUREE_CRENEAU_MIN
        rentabilite = (rev_pub / cout) if cout > 0 else 0.0
        return {
            "title":         prog["title"],
            "genre":         prog["genre"],
            "color":         COULEURS_GENRES.get(prog["genre"], "#AAAAAA"),
            "start":         minutes_en_hhmm(min_debut),
            "end":           minutes_en_hhmm(min_fin),
            "slots":         creneaux,
            "duration":      prog["duration_minutes"],
            "cost":          cout,
            "ad_revenue":    rev_pub,
            "profit":        rev_pub - cout,
            "profitability": round(rentabilite, 2),
            "audience":      prog["base_audience"],
            "ad_minutes":    prog.get("ad_minutes", 0),
        }

    for idx_jour in range(NB_JOURS):
        date_jour = debut_semaine + timedelta(days=idx_jour)

        # Programmes sélectionnés ce jour par MiniZinc (hors JT fixes)
        autres = [
            (idx_prog, programmes[idx_prog])
            for idx_prog in range(len(programmes))
            if solution[idx_jour][idx_prog] == 1
            and idx_prog != id_jt13
            and idx_prog != id_jt20
        ]

        slots_jt13 = durees[id_jt13]  # 1 créneau (30 min)
        slots_jt20 = durees[id_jt20]  # 2 créneaux (35 min → ceil = 2)

       
        fenetres = [
            (0,                        SLOT_JT13),           # matin      06:00–13:00
            (SLOT_JT13 + slots_jt13,   SLOT_JT20),           # après-midi 13:30–20:00
            (SLOT_JT20 + slots_jt20,   CRENEAUX_PAR_JOUR),   # soirée     20:30–00:00
        ]

      
        programmes_jour = []
        iter_autres     = iter(autres)
        prog_en_cours   = next(iter_autres, None)

        for (debut_fenetre, fin_fenetre) in fenetres:
            slot = debut_fenetre
            while prog_en_cours is not None and slot < fin_fenetre:
                idx_prog, prog = prog_en_cours
                nb_slots = durees[idx_prog]
                if slot + nb_slots <= fin_fenetre:
                 
                    programmes_jour.append(construire_entree(prog, idx_prog, slot))
                    slot += nb_slots
                    prog_en_cours = next(iter_autres, None)
                else:
                  
                    prog_en_cours = next(iter_autres, None)

         
            if debut_fenetre == 0:
                programmes_jour.append(construire_entree(programmes[id_jt13], id_jt13, SLOT_JT13))
            elif debut_fenetre == SLOT_JT13 + slots_jt13:
                programmes_jour.append(construire_entree(programmes[id_jt20], id_jt20, SLOT_JT20))

  
        programmes_jour.sort(key=lambda p: p["start"])

        cout_jour        = sum(p["cost"]       for p in programmes_jour)
        rev_pub_jour     = sum(p["ad_revenue"] for p in programmes_jour)
        benefice_jour    = sum(p["profit"]     for p in programmes_jour)
        audience_jour    = sum(p["audience"]   for p in programmes_jour)
        creneaux_utilises = sum(p["slots"]     for p in programmes_jour)
        rentabilite_jour = round(rev_pub_jour / cout_jour, 2) if cout_jour > 0 else 0.0

        entree_jour = {
            "name":             NOMS_JOURS[idx_jour],
            "date":             str(date_jour),
            "programs":         programmes_jour,
            "total_cost":       cout_jour,
            "total_ad_revenue": rev_pub_jour,
            "total_profit":     benefice_jour,
            "total_audience":   audience_jour,
            "profitability":    rentabilite_jour,
            "slots_used":       creneaux_utilises,
        }
        planning["jours"].append(entree_jour)

        planning["total_cout"]       += cout_jour
        planning["total_revenu_pub"] += rev_pub_jour
        planning["total_benefice"]   += benefice_jour
        planning["total_audience"]   += audience_jour


    planning["total_cost"]       = planning["total_cout"]
    planning["total_ad_revenue"] = planning["total_revenu_pub"]
    planning["total_profit"]     = planning["total_benefice"]
    planning["rentabilite"]      = (
        round(planning["total_revenu_pub"] / planning["total_cout"], 2)
        if planning["total_cout"] > 0 else 0.0
    )
    planning["profitability"] = planning["rentabilite"]

    return planning




def sauvegarder_planning(planning: dict, chemin_sortie: str):
    """
    Écrit le planning complet dans un fichier JSON lisible.

    Arguments :
        planning      (dict) : planning produit par construire_planning()
        chemin_sortie (str)  : chemin du fichier de sortie (ex. "schedule.json")
    """
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        json.dump(planning, f, ensure_ascii=False, indent=2)
    print(f"[export] Planning sauvegardé dans '{chemin_sortie}'")



def solve(
    programs_path: str      = "data/programs.json",
    model_path: str         = "model.mzn",
    output_path: str        = "schedule.json",
    time_limit: int         = 300,
    week_start: date | None = None,
) -> dict | None:
    """
    Pipeline complet : charger → préparer → résoudre → construire → sauvegarder.

    Arguments :
        programs_path (str)        : chemin vers le catalogue de programmes JSON
        model_path    (str)        : chemin vers le modèle MiniZinc (.mzn)
        output_path   (str)        : chemin du fichier JSON de sortie
        time_limit    (int)        : timeout du solveur en secondes (défaut 300s)
        week_start    (date|None)  : date du lundi de la semaine à planifier
                                     Si None, utilise le prochain lundi.

    Retourne :
        dict  : planning complet (voir construire_planning() pour la structure)
        None  : si le solveur n'a pas trouvé de solution
    """
    if week_start is None:
        aujourd_hui = date.today()
        week_start  = aujourd_hui + timedelta(days=(7 - aujourd_hui.weekday()))

    programmes_bruts    = charger_programmes(programs_path)
    programmes, donnees = construire_donnees_minizinc(programmes_bruts)
    solution            = lancer_solveur(model_path, donnees, limite_secondes=time_limit)

    if solution is None:
        return None


    planning = construire_planning(solution, programmes, donnees, week_start)
    sauvegarder_planning(planning, output_path)
    return planning


if __name__ == "__main__":
    resultat = solve()
    if resultat:
        print(f"\nCoût total :          {resultat['total_cout']:,} €")
        print(f"Revenu pub total :    {resultat['total_revenu_pub']:,} €")
        print(f"Bénéfice total :      {resultat['total_benefice']:,} €")
        print(f"Rentabilité :         {resultat['rentabilite']:.2f}×")
