import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

from db import all_models, all_prompts, color_map, query

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "llm"))
from prompts import PROMPT_VARIANTS  # noqa: E402

st.title("Comparaison des variantes de prompt")

models = all_models()
prompts = all_prompts()
prompt_colors = color_map(tuple(prompts))

st.sidebar.header("Filtres")
sel_models = st.sidebar.multiselect("Modeles", models, default=models)

if not sel_models:
    st.warning("Selectionne au moins un modele.")
    st.stop()

with st.expander("Formulation des prompts testes"):
    for key, variant in PROMPT_VARIANTS.items():
        st.markdown(f"**{variant['label']}** (`{key}`) -- {variant['description']}")

model_ph = ", ".join(["?"] * len(sel_models))
df = query(
    f"""
    SELECT prompt_variant, model_name, ai_correct, response_time
    FROM stg_ai_responses
    WHERE model_name IN ({model_ph})
    """,
    sel_models,
)

by_prompt = df.groupby(["prompt_variant", "model_name"], as_index=False).agg(
    taux_reussite=("ai_correct", "mean"), n=("ai_correct", "size"), temps_moyen=("response_time", "mean")
)

c1, c2 = st.columns(2)
with c1:
    fig = px.bar(
        by_prompt,
        x="prompt_variant",
        y="taux_reussite",
        color="prompt_variant",
        color_discrete_map=prompt_colors,
        facet_col="model_name" if len(sel_models) > 1 else None,
        text_auto=".1%",
        labels={"taux_reussite": "Taux de reussite", "prompt_variant": "Prompt"},
        title="Taux de reussite par prompt",
    )
    fig.update_layout(showlegend=False, yaxis_tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)

with c2:
    fig2 = px.bar(
        by_prompt,
        x="prompt_variant",
        y="temps_moyen",
        color="prompt_variant",
        color_discrete_map=prompt_colors,
        facet_col="model_name" if len(sel_models) > 1 else None,
        text_auto=".1f",
        labels={"temps_moyen": "Temps de reponse moyen (s)", "prompt_variant": "Prompt"},
        title="Temps de reponse moyen par prompt",
    )
    fig2.update_layout(showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)

st.caption(
    "Attention a l'interpretation : la correction se fait par inclusion (la bonne "
    "reponse apparait dans la reponse du modele). Le prompt 'naive' produit des "
    "phrases completes plus longues, ce qui peut mecaniquement augmenter ses "
    "chances de contenir la bonne reponse par rapport a 'strict_format', qui force "
    "une reponse courte -- l'ecart mesure n'est donc pas entierement imputable a "
    "une difference de 'qualite' de reponse."
)

st.subheader("Donnees")
st.dataframe(
    by_prompt.rename(
        columns={
            "prompt_variant": "Prompt",
            "model_name": "Modele",
            "taux_reussite": "Taux de reussite",
            "n": "N",
            "temps_moyen": "Temps moyen (s)",
        }
    ),
    use_container_width=True,
    hide_index=True,
)
