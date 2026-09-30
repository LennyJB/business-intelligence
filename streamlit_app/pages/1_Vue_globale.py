import plotly.express as px
import streamlit as st

from db import all_models, all_prompts, color_map, query

st.title("Vue globale")

models = all_models()
prompts = all_prompts()
model_colors = color_map(tuple(models))

st.sidebar.header("Filtres")
sel_models = st.sidebar.multiselect("Modeles", models, default=models)
sel_prompts = st.sidebar.multiselect("Variantes de prompt", prompts, default=prompts)

if not sel_models or not sel_prompts:
    st.warning("Selectionne au moins un modele et une variante de prompt.")
    st.stop()

model_ph = ", ".join(["?"] * len(sel_models))
prompt_ph = ", ".join(["?"] * len(sel_prompts))
df = query(
    f"""
    SELECT model_name, prompt_variant, ai_correct, response_time
    FROM stg_ai_responses
    WHERE model_name IN ({model_ph}) AND prompt_variant IN ({prompt_ph})
    """,
    sel_models + sel_prompts,
)

col1, col2, col3 = st.columns(3)
col1.metric("Reponses (filtre courant)", len(df))
col2.metric("Taux de reussite", f"{df['ai_correct'].mean():.1%}")
col3.metric("Temps de reponse moyen", f"{df['response_time'].mean():.1f} s")

by_model = df.groupby("model_name", as_index=False).agg(
    taux_reussite=("ai_correct", "mean"), n=("ai_correct", "size"), temps_moyen=("response_time", "mean")
)

c1, c2 = st.columns(2)
with c1:
    fig = px.bar(
        by_model.sort_values("taux_reussite"),
        x="taux_reussite",
        y="model_name",
        orientation="h",
        color="model_name",
        color_discrete_map=model_colors,
        text_auto=".1%",
        labels={"taux_reussite": "Taux de reussite", "model_name": "Modele"},
        title="Taux de reussite par modele",
    )
    fig.update_layout(showlegend=False, xaxis_tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)

with c2:
    fig2 = px.bar(
        by_model.sort_values("temps_moyen"),
        x="temps_moyen",
        y="model_name",
        orientation="h",
        color="model_name",
        color_discrete_map=model_colors,
        text_auto=".1f",
        labels={"temps_moyen": "Temps de reponse moyen (s)", "model_name": "Modele"},
        title="Temps de reponse moyen par modele",
    )
    fig2.update_layout(showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Donnees")
st.dataframe(
    by_model.rename(
        columns={"model_name": "Modele", "taux_reussite": "Taux de reussite", "n": "N", "temps_moyen": "Temps moyen (s)"}
    ),
    use_container_width=True,
    hide_index=True,
)
