import streamlit as st

from db import query

st.set_page_config(page_title="Benchmark LLM - Trivia", layout="wide")

st.title("Benchmark d'un LLM local sur des questions de culture generale")
st.markdown(
    """
Ce dashboard presente les resultats d'un benchmark comparant les performances
d'un (ou plusieurs) modele(s) LLM local (via LMStudio) sur des questions
issues d'[Open Trivia Database](https://opentdb.com/), avec plusieurs
variantes de prompt testees.

Utilisez le menu a gauche pour naviguer : **vue globale**, **par categorie**,
**par difficulte**, **comparaison de prompts**, **comparaison de modeles**.
"""
)

n_questions = query("SELECT count(*) AS n FROM stg_questions")["n"].iloc[0]
overview = query("SELECT * FROM fct_model_performance ORDER BY taux_reussite DESC")
n_reponses = int(overview["n_reponses"].sum())

col1, col2, col3, col4 = st.columns(4)
col1.metric("Questions dans le dataset", f"{n_questions:,}".replace(",", " "))
col2.metric("Modeles testes", len(overview))
col3.metric("Reponses generees", n_reponses)
col4.metric("Meilleur taux de reussite", f"{overview['taux_reussite'].max():.1%}")

display_df = overview.assign(taux_reussite=overview["taux_reussite"] * 100).rename(
    columns={
        "model_name": "Modele",
        "n_reponses": "Reponses",
        "n_correctes": "Correctes",
        "taux_reussite": "Taux de reussite",
        "temps_moyen_s": "Temps moyen (s)",
        "temps_median_s": "Temps median (s)",
    }
)

st.subheader("Performance globale par modele")
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={"Taux de reussite": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)},
)

st.caption(
    "Methodologie : l'enrichissement LLM est effectue sur un echantillon stratifie "
    "(categorie x difficulte) du dataset complet, pas sur son integralite -- le cout "
    "de calcul d'un run exhaustif (des heures par modele) etait disproportionne pour "
    "ce benchmark. Voir le README pour le detail."
)
