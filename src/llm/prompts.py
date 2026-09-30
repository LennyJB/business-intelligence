"""
Variantes de prompt testees dans le benchmark.

Chaque variante est identifiee par une cle stable (utilisee comme valeur de
`prompt_variant` dans le dataset enrichi) et une fonction `build(question)`
qui construit le texte envoye au modele a partir d'une ligne de la couche
silver (dict avec au moins "question", "category", "difficulty").
"""

# Consigne ajoutee pour les questions vrai/faux dans les variantes qui
# donnent deja des instructions de format (strict_format, role_expert) :
# sans elle, le modele repond souvent "Oui"/"Vrai" (en francais, la langue
# du prompt) au lieu du litteral anglais "True"/"False" attendu par
# OpenTDB, ce qui fait systematiquement echouer la comparaison.
def _boolean_hint(q):
    if q["type"] == "boolean":
        return " Reponds uniquement par True ou False (en anglais)."
    return ""


PROMPT_VARIANTS = {
    "naive": {
        "label": "Question brute",
        "description": (
            "La question posee telle quelle, sans consigne de formatage "
            "(y compris pour les questions vrai/faux : baseline volontairement non guidee)."
        ),
        "build": lambda q: q["question"],
    },
    "strict_format": {
        "label": "Format strict",
        "description": "Consigne explicite de repondre uniquement par la reponse, sans phrase.",
        "build": lambda q: (
            "Reponds uniquement par la reponse la plus courte possible, "
            "sans phrase complete ni explication." + _boolean_hint(q) + "\n"
            f"Question : {q['question']}"
        ),
    },
    "role_expert": {
        "label": "Role expert + contexte",
        "description": (
            "Prompt roleplay (expert de trivia) avec categorie et difficulte "
            "donnees en contexte, en plus de la consigne de format strict."
        ),
        "build": lambda q: (
            "Tu es un expert de culture generale qui participe a un jeu de trivia. "
            "Reponds uniquement par la reponse exacte, sans explication, sans "
            "ponctuation superflue et sans repeter la question." + _boolean_hint(q) + "\n"
            f"Categorie : {q['category']} | Difficulte : {q['difficulty']}\n"
            f"Question : {q['question']}"
        ),
    },
}


def build_prompt(variant_key, question_row):
    return PROMPT_VARIANTS[variant_key]["build"](question_row)
