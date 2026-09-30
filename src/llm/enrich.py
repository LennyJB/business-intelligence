"""
Enrichit les questions de la couche silver avec les reponses d'un modele
LMStudio : pour chaque question x variante de prompt, interroge le modele
et stocke ai_answer / ai_correct / response_time.

Un fichier de checkpoint (JSONL) est ecrit au fur et a mesure : chaque
reponse deja obtenue (meme question_id + prompt_variant + model_name) est
sautee lors d'une reprise, et le fichier accumule les resultats de tous les
runs (utile pour comparer plusieurs modeles sans tout relancer).

Usage:
    python src/llm/enrich.py --model google/gemma-4-12b-qat
    python src/llm/enrich.py --model google/gemma-4-12b-qat --sample-size 50   # test rapide
    python src/llm/enrich.py --model google/gemma-4-12b-qat --all              # dataset complet
"""

import argparse
import json
import os
import re
import sys
import time

import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from lmstudio_client import LMStudioClient
from prompts import PROMPT_VARIANTS, build_prompt

load_dotenv()

SILVER_DIR = os.environ.get("SILVER_DIR", "data/silver")
QUESTIONS_PATH = os.path.join(SILVER_DIR, "questions_clean.parquet")
OUT_PATH = os.path.join(SILVER_DIR, "ai_responses.parquet")
CHECKPOINT_PATH = os.path.join(SILVER_DIR, ".ai_responses_checkpoint.jsonl")

ARTICLES = {"a", "an", "the"}


def normalize_answer(text):
    """Normalisation style SQuAD : minuscules, sans ponctuation ni articles,
    espaces normalises. Permet de comparer 'The Beatles' et 'beatles'."""
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    words = [w for w in text.split() if w not in ARTICLES]
    return " ".join(words)


# Equivalents acceptes pour les questions vrai/faux : le prompt est en
# francais, donc meme avec une consigne de format le modele repond parfois
# "Oui"/"Vrai" plutot que le litteral anglais "True"/"False" attendu par
# OpenTDB. Filet de securite independant de la consigne de prompt.
_BOOLEAN_EQUIVALENTS = {
    "true": {"true", "vrai", "oui", "yes"},
    "false": {"false", "faux", "non", "no"},
}


def is_correct(ai_answer, correct_answer):
    """Vrai si la bonne reponse (normalisee) apparait dans la reponse du
    modele (normalisee). Une inclusion plutot qu'une egalite stricte : le
    prompt "naive" (sans consigne de format) produit souvent des phrases
    completes ("... faisait partie du mouvement Post-Impressionism") plutot
    qu'une reponse seche -- l'egalite stricte penaliserait injustement ces
    reponses correctes mais verbeuses, faussant la comparaison entre
    variantes de prompt."""
    norm_ai = normalize_answer(ai_answer)
    norm_correct = normalize_answer(correct_answer)

    if norm_correct in _BOOLEAN_EQUIVALENTS:
        ai_words = set(norm_ai.split())
        return bool(ai_words & _BOOLEAN_EQUIVALENTS[norm_correct])
    return bool(norm_correct) and norm_correct in norm_ai


def stratified_sample(df, n, seed):
    """Echantillonne n lignes en respectant les proportions categorie x difficulte,
    pour garder un dataset de test representatif de la population complete."""
    if n is None or n >= len(df):
        return df
    frac = n / len(df)
    # Boucle manuelle plutot qu'un .groupby().apply(lambda g: g.sample(...))
    # : ce dernier perd les colonnes de groupby ("category", "difficulty")
    # dans le resultat selon la version de pandas.
    parts = []
    for _, g in df.groupby(["category", "difficulty"]):
        k = min(len(g), max(1, round(len(g) * frac)))
        parts.append(g.sample(k, random_state=seed))
    sampled = pd.concat(parts)
    if len(sampled) > n:
        sampled = sampled.sample(n, random_state=seed)
    return sampled.reset_index(drop=True)


def load_checkpoint():
    rows = []
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-size", type=int, default=300,
                         help="Nb de questions a enrichir, echantillon stratifie categorie x difficulte (defaut: 300). Ignore avec --all.")
    parser.add_argument("--all", action="store_true", help="Enrichit l'integralite du dataset silver (long).")
    parser.add_argument("--prompts", default=",".join(PROMPT_VARIANTS),
                         help="Variantes de prompt a tester, separees par des virgules.")
    parser.add_argument("--model", default=os.environ.get("LMSTUDIO_MODEL"),
                         help="Nom du modele charge dans LMStudio (voir /v1/models).")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=OUT_PATH)
    args = parser.parse_args()

    if not args.model:
        print("Erreur: precise --model ou LMSTUDIO_MODEL dans .env", file=sys.stderr)
        sys.exit(1)

    variants = args.prompts.split(",")
    for v in variants:
        if v not in PROMPT_VARIANTS:
            print(f"Variante de prompt inconnue: {v} (disponibles: {list(PROMPT_VARIANTS)})", file=sys.stderr)
            sys.exit(1)

    print(f"Lecture de {QUESTIONS_PATH}...")
    df = pd.read_parquet(QUESTIONS_PATH)

    if not args.all:
        df = stratified_sample(df, args.sample_size, args.seed)
        print(f"Echantillon stratifie (categorie x difficulte): {len(df)} questions.")
    else:
        print(f"Dataset complet: {len(df)} questions.")

    total_calls = len(df) * len(variants)
    print(f"{len(df)} question(s) x {len(variants)} variante(s) de prompt = {total_calls} appels potentiels.")

    rows = load_checkpoint()
    done_keys = {(r["question_id"], r["prompt_variant"], r["model_name"]) for r in rows}
    already_done = sum(1 for k in done_keys if k[2] == args.model)
    if already_done:
        print(f"{already_done} reponse(s) deja presentes dans le checkpoint pour ce modele, seront sautees.")

    print(f"Connexion a LMStudio (modele: {args.model})...")
    client = LMStudioClient(args.model)

    os.makedirs(SILVER_DIR, exist_ok=True)
    n_new = 0
    start = time.perf_counter()

    with open(CHECKPOINT_PATH, "a", encoding="utf-8") as ckpt_f:
        for variant_key in variants:
            for _, q in df.iterrows():
                key = (q["question_id"], variant_key, args.model)
                if key in done_keys:
                    continue

                prompt = build_prompt(variant_key, q)
                try:
                    answer, elapsed = client.ask(prompt)
                except Exception as exc:
                    print(f"  echec sur {q['question_id']} ({variant_key}): {exc}")
                    continue

                row = {
                    "question_id": q["question_id"],
                    "model_name": args.model,
                    "prompt_variant": variant_key,
                    "ai_answer": answer,
                    "ai_correct": bool(is_correct(answer, q["correct_answer"])),
                    "response_time": float(elapsed),
                }
                rows.append(row)
                done_keys.add(key)
                ckpt_f.write(json.dumps(row, ensure_ascii=False) + "\n")
                ckpt_f.flush()

                n_new += 1
                if n_new % 10 == 0:
                    avg = (time.perf_counter() - start) / n_new
                    print(f"  {n_new} nouvelle(s) reponse(s) ({avg:.1f}s/appel en moyenne)")

    out_df = pd.DataFrame(rows)
    out_df.to_parquet(args.out, index=False)
    print(f"OK: {n_new} nouvelle(s) reponse(s), {len(out_df)} au total -> {args.out}")
    if len(out_df):
        this_run = out_df[out_df["model_name"] == args.model]
        print(f"Taux de reussite pour {args.model}: {this_run['ai_correct'].mean():.1%}")


if __name__ == "__main__":
    main()
