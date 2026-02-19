
import json
from pathlib import Path

import streamlit as st

import solver as slv


st.set_page_config(
    page_title="Optimiseur de Grille TV",
    page_icon="📺",
    layout="wide",
)



def formater(n: int | float, suffixe: str = "") -> str:
    """Formate un nombre avec des espaces comme séparateur de milliers."""
    return f"{int(n):,}".replace(",", "\u202f") + suffixe


def charger_planning_existant() -> dict | None:
    """Charge schedule.json depuis le disque si il existe."""
    chemin = Path("schedule.json")
    if chemin.exists():
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    return None


def badge_genre(genre: str, couleur: str) -> str:
    """Retourne un badge HTML coloré pour un genre."""
    return (
        f'<span style="background:{couleur};color:#fff;padding:2px 8px;'
        f'border-radius:10px;font-size:0.72rem;font-weight:600;">{genre}</span>'
    )


def couleur_benefice(benefice: int) -> str:
    """Vert si bénéfice positif, rouge si négatif."""
    return "#4ade80" if benefice >= 0 else "#f87171"


def barre_rentabilite(ratio: float, largeur_px: int = 120) -> str:
    """
    Retourne une mini-barre HTML représentant visuellement la rentabilité.
    ratio > 1 = rentable (vert), ratio < 1 = déficitaire (rouge).
    La barre est plafonnée à 3× pour l'affichage.
    """
    plafonne = min(ratio, 3.0)
    pct      = plafonne / 3.0 * 100
    couleur  = "#4ade80" if ratio >= 1.0 else "#f87171"
    etiquette = f"{ratio:.2f}×"
    return (
        f'<div style="display:inline-flex;align-items:center;gap:6px;">'
        f'<div style="width:{largeur_px}px;background:#2d2d3d;border-radius:4px;height:8px;">'
        f'<div style="width:{pct:.1f}%;background:{couleur};border-radius:4px;height:8px;"></div>'
        f'</div>'
        f'<span style="font-size:0.8rem;color:{couleur};font-weight:600;">{etiquette}</span>'
        f'</div>'
    )




with st.sidebar:
    st.title("⚙️ Paramètres")
    st.markdown("---")

    limite_temps = st.slider(
        "Limite de résolution (s)",
        min_value=5,
        max_value=3600,
        value=30,
        step=5,
    )

    st.markdown("---")
    bouton_generer = st.button("▶ Générer le Planning", type="primary", use_container_width=True)



st.title("📺 Optimiseur de Grille TV")
st.caption(
    "Programmation par contraintes (MiniZinc + Gecode) — maximise le bénéfice hebdomadaire "
    "tout en respectant le budget et les règles éditoriales."
)
st.markdown("---")



if bouton_generer:
    with st.spinner("Résolution en cours … veuillez patienter"):
        planning = slv.solve(
            programs_path="data/programs.json",
            model_path="model.mzn",
            output_path="schedule.json",
            time_limit=limite_temps,
        )
    if planning is None:
        st.error("Aucune solution trouvée. Essayez d'augmenter la limite de temps.")
    else:
        st.session_state["planning"] = planning
        st.success("Planning généré avec succès !")

if "planning" not in st.session_state:
    st.session_state["planning"] = charger_planning_existant()

planning = st.session_state.get("planning")




if planning is None:
    st.info("Cliquez sur **▶ Générer le Planning** dans la barre latérale pour commencer.")
    st.markdown("### Catalogue des Programmes")
    chemin_progs = Path("data/programs.json")
    if chemin_progs.exists():
        with open(chemin_progs, encoding="utf-8") as f:
            progs = json.load(f)
        lignes = [
            {
                "Titre":          p["title"],
                "Genre":          p["genre"],
                "Durée":          f"{p['duration_minutes']} min",
                "Coût (€)":       formater(p["cost"]),
                "Audience":       formater(p["base_audience"]),
                "Min pub":        p.get("ad_minutes", 0),
                "Rev. pub (€)":   formater(slv.compute_ad_revenue(p)),
                "Bénéfice (€)":   formater(slv.compute_ad_revenue(p) - p["cost"]),
            }
            for p in progs
        ]
        st.dataframe(lignes, use_container_width=True, hide_index=True)
    st.stop()




st.markdown(f"### Semaine du {planning.get('week_start', planning.get('semaine_debut', ''))}")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Coût total",    formater(planning["total_cost"], " €"))
c2.metric("Revenus pub",   formater(planning["total_ad_revenue"], " €"))

benefice_semaine = planning["total_profit"]
c3.metric(
    "Bénéfice net",
    formater(benefice_semaine, " €"),
    delta=formater(benefice_semaine, " €"),
    delta_color="normal" if benefice_semaine >= 0 else "inverse",
)
c4.metric(
    "Rentabilité",
    f"{planning['profitability']:.2f}×",
    help="Revenus pub ÷ coût d'acquisition. >1 = rentable.",
)
c5.metric("Audience totale", formater(planning["total_audience"], " spectateurs"))


pct_budget = min(planning["total_cost"] / slv.WEEKLY_BUDGET, 1.0)
st.progress(
    pct_budget,
    text=f"Budget utilisé : {formater(planning['total_cost'])} / {formater(slv.WEEKLY_BUDGET)} €  "
         f"({pct_budget * 100:.1f} %)",
)

st.markdown("---")




st.markdown("### Rentabilité par Jour")

colonnes_jours = st.columns(7)
for i, jour in enumerate(planning["days"]):
    ratio    = jour["profitability"]
    benefice = jour["total_profit"]
    couleur  = "#4ade80" if benefice >= 0 else "#f87171"
    with colonnes_jours[i]:
        st.markdown(
            f'<div style="background:#1e1e2e;border-radius:10px;padding:10px 6px;'
            f'text-align:center;border-top:4px solid {couleur};">'
            f'<div style="font-size:0.8rem;color:#aaa;">{jour["name"]}</div>'
            f'<div style="font-size:1.1rem;font-weight:700;color:{couleur};">'
            f'{formater(benefice)} €</div>'
            f'<div style="font-size:0.75rem;color:{couleur};">{ratio:.2f}×</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("---")




st.markdown("### Planning Journalier")

noms_jours      = [j["name"] for j in planning["days"]]
nom_jour_selec  = st.radio("Jour", noms_jours, horizontal=True, label_visibility="collapsed")
jour_selec      = next(j for j in planning["days"] if j["name"] == nom_jour_selec)


m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Programmes",    len(jour_selec["programs"]))
m2.metric("Coût",          formater(jour_selec["total_cost"], " €"))
m3.metric("Revenus pub",   formater(jour_selec["total_ad_revenue"], " €"))

benefice_jour = jour_selec["total_profit"]
m4.metric(
    "Bénéfice net",
    formater(benefice_jour, " €"),
    delta=formater(benefice_jour, " €"),
    delta_color="normal" if benefice_jour >= 0 else "inverse",
)
m5.metric("Rentabilité", f"{jour_selec['profitability']:.2f}×")

st.caption(
    f"📅 {jour_selec['date']}  ·  "
    f"Créneaux utilisés : {jour_selec['slots_used']} / {slv.SLOTS_PER_DAY}  "
    f"({jour_selec['slots_used'] * slv.SLOT_MINUTES} / "
    f"{slv.SLOTS_PER_DAY * slv.SLOT_MINUTES} min)"
)

st.markdown("")


if not jour_selec["programs"]:
    st.warning("Aucun programme planifié pour ce jour.")
else:
    for prog in jour_selec["programs"]:
        couleur      = prog["color"]
        p_benefice   = prog["profit"]
        col_benefice = couleur_benefice(p_benefice)
        signe        = "+" if p_benefice >= 0 else ""
        ratio        = prog["profitability"]

        html = f"""
        <div style="
            border-left: 5px solid {couleur};
            background: #1e1e2e;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
        ">
          <!-- GAUCHE : horaire + titre -->
          <div style="flex:1;min-width:0;">
            <div style="font-size:0.9rem;font-weight:700;color:#fff;white-space:nowrap;">
              {prog['start']} – {prog['end']} &nbsp; {badge_genre(prog['genre'], couleur)}
            </div>
            <div style="font-size:1.05rem;color:#eee;margin-top:3px;
                        white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
              {prog['title']}
            </div>
            <div style="font-size:0.75rem;color:#888;margin-top:2px;">
              {prog['duration']} min · {prog['slots']} créneaux · {prog['ad_minutes']} min pub
            </div>
          </div>

          <!-- CENTRE : barre de rentabilité -->
          <div style="text-align:center;min-width:160px;">
            <div style="font-size:0.7rem;color:#888;margin-bottom:3px;">RENTABILITÉ</div>
            {barre_rentabilite(ratio, largeur_px=120)}
          </div>

          <!-- DROITE : chiffres financiers -->
          <div style="text-align:right;min-width:130px;">
            <div style="font-size:0.75rem;color:#aaa;">💰 Coût</div>
            <div style="font-size:0.9rem;color:#fff;">{formater(prog['cost'])} €</div>
            <div style="font-size:0.75rem;color:#aaa;margin-top:4px;">📢 Revenus pub</div>
            <div style="font-size:0.9rem;color:#fff;">{formater(prog['ad_revenue'])} €</div>
            <div style="font-size:0.75rem;color:#aaa;margin-top:4px;">📈 Bénéfice</div>
            <div style="font-size:0.95rem;font-weight:700;color:{col_benefice};">
              {signe}{formater(p_benefice)} €
            </div>
          </div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)

st.markdown("---")




st.markdown("### Récapitulatif de la Semaine")

lignes = []
for j in planning["days"]:
    b = j["total_profit"]
    lignes.append({
        "Jour":            j["name"],
        "Date":            j["date"],
        "Programmes":      len(j["programs"]),
        "Coût (€)":        formater(j["total_cost"]),
        "Revenus pub (€)": formater(j["total_ad_revenue"]),
        "Bénéfice (€)":    ("+" if b >= 0 else "") + formater(b),
        "Rentabilité":     f"{j['profitability']:.2f}×",
        "Audience":        formater(j["total_audience"]),
        "Créneaux":        f"{j['slots_used']} / {slv.SLOTS_PER_DAY}",
    })
st.dataframe(lignes, use_container_width=True, hide_index=True)

st.markdown("---")




colonnes = st.columns(len(slv.GENRE_COLORS))
for i, (genre, couleur) in enumerate(slv.GENRE_COLORS.items()):
    with colonnes[i]:
        st.markdown(
            f'<div style="background:{couleur};color:#fff;text-align:center;'
            f'padding:5px 0;border-radius:6px;font-size:0.78rem;font-weight:600;">'
            f'{genre}</div>',
            unsafe_allow_html=True,
        )
