import plotly.express as px
import streamlit as st

from db import all_models, color_map, query

st.title("Comparaison des modeles")

models = all_models()
model_colors = color_map(tuple(models))

if len(models) < 2:
    st.info(
        "Un seul modele a ete benchmarke pour l'instant. Charge un autre modele dans "
        "LMStudio et relance `enrich.py --model <nom>` pour enrichir cette page -- "
        "les resultats existants ne seront pas recalcules (voir README)."
    )

perf = query("SELECT * FROM fct_model_performance ORDER BY taux_reussite DESC")

st.subheader("Precision vs vitesse")
fig = px.scatter(
    perf,
    x="temps_moyen_s",
    y="taux_reussite",
    color="model_name",
    color_discrete_map=model_colors,
    size="n_reponses",
    size_max=40,
    labels={
        "temps_moyen_s": "Temps de reponse moyen (s)",
        "taux_reussite": "Taux de reussite",
        "model_name": "Modele",
        "n_reponses": "Reponses",
    },
    title="Chaque point = un modele (taille = nombre de reponses)",
)
fig.update_layout(yaxis_tickformat=".0%")
fig.update_traces(marker=dict(line=dict(width=1, color="white")))
st.plotly_chart(fig, use_container_width=True)
st.caption(
    "Le modele ideal serait en haut a gauche (rapide et precis). Un modele plus "
    "petit/rapide n'est pas forcement moins precis -- voir le README pour la "
    "discussion de ce resultat sur ce benchmark."
)

st.subheader("Tableau comparatif")
st.dataframe(
    perf.assign(taux_reussite=perf["taux_reussite"] * 100).rename(
        columns={
            "model_name": "Modele",
            "n_reponses": "Reponses",
            "n_correctes": "Correctes",
            "taux_reussite": "Taux de reussite",
            "temps_moyen_s": "Temps moyen (s)",
            "temps_median_s": "Temps median (s)",
        }
    ),
    use_container_width=True,
    hide_index=True,
    column_config={"Taux de reussite": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)},
)
