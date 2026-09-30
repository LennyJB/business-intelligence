import plotly.express as px
import streamlit as st

from db import all_models, all_prompts, color_map, query

st.title("Precision par categorie")

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
    SELECT category, model_name, ai_correct
    FROM stg_responses_enriched
    WHERE model_name IN ({model_ph}) AND prompt_variant IN ({prompt_ph})
    """,
    sel_models + sel_prompts,
)

by_cat = df.groupby(["category", "model_name"], as_index=False).agg(
    taux_reussite=("ai_correct", "mean"), n=("ai_correct", "size")
)

# Ordonne les categories par taux de reussite moyen (toutes selections confondues)
# pour une lecture immediate, du meilleur au pire.
order = by_cat.groupby("category")["taux_reussite"].mean().sort_values().index.tolist()

height = max(400, 24 * len(order))
fig = px.bar(
    by_cat,
    x="taux_reussite",
    y="category",
    color="model_name" if len(sel_models) > 1 else None,
    color_discrete_map=model_colors if len(sel_models) > 1 else None,
    orientation="h",
    barmode="group",
    category_orders={"category": order},
    labels={"taux_reussite": "Taux de reussite", "category": "Categorie", "model_name": "Modele"},
    hover_data={"n": True},
    title="Taux de reussite par categorie" + (" et par modele" if len(sel_models) > 1 else ""),
)
if len(sel_models) == 1:
    fig.update_traces(marker_color="#2a78d6")
fig.update_layout(xaxis_tickformat=".0%", height=height)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Donnees")
st.dataframe(
    by_cat.sort_values("taux_reussite", ascending=False).rename(
        columns={"category": "Categorie", "model_name": "Modele", "taux_reussite": "Taux de reussite", "n": "N"}
    ),
    use_container_width=True,
    hide_index=True,
)
