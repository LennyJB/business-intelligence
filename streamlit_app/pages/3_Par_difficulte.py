import plotly.express as px
import streamlit as st

from db import all_models, all_prompts, color_map, query

st.title("Precision par difficulte")

DIFFICULTY_ORDER = ["easy", "medium", "hard"]

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
    SELECT difficulty, model_name, ai_correct
    FROM stg_responses_enriched
    WHERE model_name IN ({model_ph}) AND prompt_variant IN ({prompt_ph})
    """,
    sel_models + sel_prompts,
)

by_diff = df.groupby(["difficulty", "model_name"], as_index=False).agg(
    taux_reussite=("ai_correct", "mean"), n=("ai_correct", "size")
)

fig = px.bar(
    by_diff,
    x="difficulty",
    y="taux_reussite",
    color="model_name" if len(sel_models) > 1 else None,
    color_discrete_map=model_colors if len(sel_models) > 1 else None,
    barmode="group",
    category_orders={"difficulty": DIFFICULTY_ORDER},
    labels={"taux_reussite": "Taux de reussite", "difficulty": "Difficulte", "model_name": "Modele"},
    hover_data={"n": True},
    text_auto=".1%",
    title="Taux de reussite par difficulte" + (" et par modele" if len(sel_models) > 1 else ""),
)
if len(sel_models) == 1:
    fig.update_traces(marker_color="#2a78d6")
fig.update_layout(yaxis_tickformat=".0%")
st.plotly_chart(fig, use_container_width=True)

st.caption(
    "Un taux de reussite qui decroit regulierement de 'easy' a 'hard' est un bon "
    "signe de coherence : ca confirme que la difficulte annoncee par OpenTDB "
    "reflete une vraie difficulte pour le modele, et que le pipeline de correction "
    "n'introduit pas de bruit qui l'ecraserait."
)

st.subheader("Donnees")
st.dataframe(
    by_diff.rename(
        columns={"difficulty": "Difficulte", "model_name": "Modele", "taux_reussite": "Taux de reussite", "n": "N"}
    ),
    use_container_width=True,
    hide_index=True,
)
