"""
Scrape l'integralite du dataset OpenTDB et l'ecrit dans la couche bronze.

Boucle sur chaque combinaison (categorie x difficulte x type de question),
interroge l'API par lots de 50 jusqu'a epuisement du token de session pour
cette combinaison, et sauvegarde :
  - les payloads bruts de chaque requete dans data/bronze/raw_json/
  - le dataset aplati dans data/bronze/questions_raw.csv

Usage:
    python src/scraping/scrape_bronze.py                 # scraping complet
    python src/scraping/scrape_bronze.py --sample 3       # test rapide (3 categories)
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from opentdb_client import DIFFICULTIES, QUESTION_TYPES, RC_SUCCESS, OpenTDBClient

BRONZE_DIR = os.environ.get("BRONZE_DIR", "data/bronze")
RAW_JSON_DIR = os.path.join(BRONZE_DIR, "raw_json")
CSV_PATH = os.path.join(BRONZE_DIR, "questions_raw.csv")

CSV_FIELDS = [
    "category", "type", "difficulty", "question",
    "correct_answer", "incorrect_answers", "scraped_at",
]


def scrape_combo(client, token, category, difficulty, qtype, amount, dump_index):
    """Recupere toutes les questions disponibles pour une combinaison donnee.

    L'API OpenTDB a un piege documente : si `amount` demande depasse le
    nombre de questions restantes (non deja vues par le token) pour le
    filtre, elle repond response_code=1 (aucun resultat) plutot que de
    renvoyer le reste disponible (jamais de resultat partiel). Comme le
    rate-limit (5s) s'applique par requete, qu'elle reussisse ou non, la
    strategie efficace est de minimiser le nombre d'appels :
      1. Sonde d'existence (amount=1) : beaucoup de combinaisons categorie x
         difficulte x type n'ont aucune question sur OpenTDB. Un seul appel
         permet d'ecarter ces combinaisons vides immediatement.
      2. Phase "bulk" : lots de `amount`, tant que ca reussit (efficace pour
         les grosses combinaisons).
      3. Phase "reste" : decomposition binaire du reliquat (< amount) -- un
         seul appel par palier de puissance de 2 (32,16,8,4,2,1), sans
         tatonnement : chaque palier est teste exactement une fois.
    """
    rows = []

    def save_batch(questions):
        dump_index[0] += 1
        dump_path = os.path.join(RAW_JSON_DIR, f"batch_{dump_index[0]:05d}.json")
        with open(dump_path, "w", encoding="utf-8") as f:
            json.dump(
                {"category": category, "difficulty": difficulty, "type": qtype, "questions": questions},
                f, ensure_ascii=False, indent=2,
            )
        now = datetime.now(timezone.utc).isoformat()
        for q in questions:
            rows.append({
                "category": q["category"],
                "type": q["type"],
                "difficulty": q["difficulty"],
                "question": q["question"],
                "correct_answer": q["correct_answer"],
                # JSON plutot qu'un join par un separateur simple: certaines
                # reponses OpenTDB contiennent elles-memes des caracteres comme
                # "|" (ex: "882 ft | 268.8 m"), ce qui casserait un split naif.
                "incorrect_answers": json.dumps(q["incorrect_answers"], ensure_ascii=False),
                "scraped_at": now,
            })

    def request(size):
        return client.fetch_questions(
            amount=size, category=category, difficulty=difficulty,
            qtype=qtype, token=token,
        )

    # 1. Sonde d'existence.
    rc, questions = request(1)
    if not (rc == RC_SUCCESS and questions):
        return rows  # Combinaison vide: un seul appel consomme.
    save_batch(questions)

    # 2. Phase bulk.
    while True:
        rc, questions = request(amount)
        if rc == RC_SUCCESS and questions:
            save_batch(questions)
        else:
            break

    # 3. Phase reste: decomposition binaire, un appel par palier.
    tier = 1
    while tier * 2 <= amount:
        tier *= 2
    while tier >= 1:
        rc, questions = request(tier)
        if rc == RC_SUCCESS and questions:
            save_batch(questions)
        tier //= 2

    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amount", type=int, default=50, help="Questions par requete (max API: 50)")
    parser.add_argument("--sample", type=int, default=None,
                         help="Limite le scraping aux N premieres categories (test rapide)")
    args = parser.parse_args()

    os.makedirs(RAW_JSON_DIR, exist_ok=True)

    client = OpenTDBClient()

    print("Recuperation de la liste des categories...")
    categories = client.get_categories()
    if args.sample:
        categories = categories[: args.sample]
    print(f"{len(categories)} categorie(s) a scraper.")

    print("Demande d'un token de session...")
    token = client.request_session_token()

    dump_index = [0]
    total_rows = 0
    start = time.perf_counter()

    # Ecriture incrementale : une combinaison ratee (ou une coupure reseau)
    # ne fait pas perdre le travail deja scrape.
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()

        for cat in categories:
            for difficulty in DIFFICULTIES:
                for qtype in QUESTION_TYPES:
                    combo_label = f"{cat['name']} / {difficulty} / {qtype}"
                    try:
                        rows = scrape_combo(client, token, cat["id"], difficulty, qtype, args.amount, dump_index)
                    except Exception as exc:
                        print(f"  {combo_label}: ECHEC ({exc}) -- combinaison ignoree")
                        continue
                    if rows:
                        print(f"  {combo_label}: {len(rows)} question(s)")
                        writer.writerows(rows)
                        f.flush()
                        total_rows += len(rows)

    print(f"OK: {total_rows} questions scrapees en {time.perf_counter() - start:.1f}s -> {CSV_PATH}")


if __name__ == "__main__":
    main()
