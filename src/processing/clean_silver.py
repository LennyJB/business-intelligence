"""
Nettoie la couche bronze (questions_raw.csv) et produit la couche silver
(questions_clean.parquet).

Traitements : suppression des doublons exacts, normalisation des champs
categoriels, generation d'un question_id stable, melange reproductible
des choix de reponse (bonne reponse + mauvaises reponses).

Usage:
    python src/processing/clean_silver.py
"""

import argparse
import hashlib
import json
import os
import random

import pandas as pd

BRONZE_CSV = os.environ.get("BRONZE_CSV", "data/bronze/questions_raw.csv")
SILVER_DIR = os.environ.get("SILVER_DIR", "data/silver")
OUT_PATH = os.path.join(SILVER_DIR, "questions_clean.parquet")


def make_question_id(category, question):
    digest = hashlib.sha256(f"{category}::{question}".encode("utf-8")).hexdigest()
    return digest[:16]


def build_choices(row):
    """Melange bonne reponse + mauvaises reponses, avec une graine derivee
    du question_id pour que le melange soit reproductible entre les runs."""
    incorrect = [a.strip() for a in json.loads(row["incorrect_answers"]) if a.strip()]
    choices = incorrect + [row["correct_answer"].strip()]
    rng = random.Random(row["question_id"])
    rng.shuffle(choices)
    return choices


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="in_path", default=BRONZE_CSV)
    parser.add_argument("--out", dest="out_path", default=OUT_PATH)
    args = parser.parse_args()

    os.makedirs(SILVER_DIR, exist_ok=True)

    print(f"Lecture de {args.in_path}...")
    df = pd.read_csv(args.in_path, dtype=str, keep_default_na=False)
    print(f"{len(df)} lignes brutes.")

    for col in ("category", "type", "difficulty", "question", "correct_answer", "incorrect_answers"):
        df[col] = df[col].str.strip()

    before = len(df)
    df = df.drop_duplicates(subset=["category", "type", "difficulty", "question", "correct_answer"])
    print(f"{before - len(df)} doublon(s) exact(s) supprime(s).")

    df["question_id"] = [make_question_id(c, q) for c, q in zip(df["category"], df["question"])]
    dup_ids = df["question_id"].duplicated().sum()
    if dup_ids:
        print(f"Attention: {dup_ids} collision(s) de question_id (memes categorie+question, contenu differe).")
        df = df.drop_duplicates(subset=["question_id"])

    df["choices"] = df.apply(build_choices, axis=1)
    df["n_choices"] = df["choices"].apply(len)

    bad = df[((df["type"] == "multiple") & (df["n_choices"] != 4)) |
             ((df["type"] == "boolean") & (df["n_choices"] != 2))]
    if len(bad):
        print(f"Attention: {len(bad)} question(s) avec un nombre de choix inattendu.")

    df = df[["question_id", "category", "type", "difficulty", "question",
             "correct_answer", "choices", "scraped_at"]]

    df.to_parquet(args.out_path, index=False)
    print(f"OK: {len(df)} questions nettoyees -> {args.out_path}")


if __name__ == "__main__":
    main()
