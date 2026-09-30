"""
Connexion partagee a la couche gold (DuckDB) et palette de couleurs stable
pour le dashboard.
"""

import os

import duckdb
import streamlit as st

GOLD_DB = os.environ.get(
    "GOLD_DB", os.path.join(os.path.dirname(__file__), "..", "data", "gold", "benchmark.duckdb")
)

# Palette categorielle validee (accessible daltonisme), assignee dans cet
# ordre fixe. La couleur suit l'entite (modele/prompt), jamais son rang :
# on construit le mapping a partir de l'univers COMPLET des valeurs (non
# filtre), pour qu'un filtre qui reduit la selection ne repeigne jamais
# les entites restantes.
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]


@st.cache_resource
def get_connection():
    return duckdb.connect(GOLD_DB, read_only=True)


def query(sql, params=None):
    con = get_connection()
    return con.execute(sql, params or []).df()


@st.cache_data
def color_map(values):
    """Associe une couleur stable a chaque valeur (triee alphabetiquement),
    en piochant dans PALETTE dans l'ordre. `values` doit couvrir l'univers
    complet (non filtre) pour rester stable d'une page/d'un filtre a l'autre."""
    ordered = sorted(set(values))
    return {v: PALETTE[i % len(PALETTE)] for i, v in enumerate(ordered)}


@st.cache_data
def all_models():
    return query("SELECT DISTINCT model_name FROM stg_ai_responses ORDER BY model_name")["model_name"].tolist()


@st.cache_data
def all_prompts():
    return query("SELECT DISTINCT prompt_variant FROM stg_ai_responses ORDER BY prompt_variant")[
        "prompt_variant"
    ].tolist()
