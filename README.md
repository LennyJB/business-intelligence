# Trivial Poursuite — Benchmark d'un LLM local sur OpenTDB

Projet M2 DEV : pipeline complet de data engineering pour benchmarker un modèle
d'IA local (via [LMStudio](https://lmstudio.ai/)) sur des questions de culture
générale issues d'[Open Trivia Database](https://opentdb.com/), avec un focus
sur l'impact de la formulation du prompt.

## Résultats en un coup d'œil

| Modèle | Réponses | Taux de réussite | Temps moyen |
|---|---|---|---|
| `google/gemma-3-4b` | 633 | **34,4 %** | 6,95 s |
| `google/gemma-4-12b-qat` | 103 | **27,2 %** | 88,31 s |

- **Le prompt le plus permissif ("naive", sans consigne) gagne** sur `gemma-3-4b`
  (37,0 % vs 34,1 % pour `strict_format` et 32,2 % pour `role_expert`) — voir la
  limite méthodologique ci-dessous, ce résultat est à nuancer.
- **La précision décroît avec la difficulté annoncée par OpenTDB** (41,4 % easy
  → 32,6 % medium → 27,4 % hard sur `gemma-3-4b`) : un bon signe de cohérence
  du pipeline de correction.
- Le modèle 12B, malgré sa taille, ne fait **pas mieux** que le 4B sur ce
  benchmark — voir la section [Limites](#limites--points-dattention) pour le
  contexte (échantillon plus petit, run interrompu).

Le dashboard Streamlit (`streamlit_app/`) permet d'explorer ces résultats de
façon interactive, filtrés par modèle/prompt/catégorie/difficulté.

## Architecture (médaillon)

```
Bronze                Silver                        Gold (dbt + DuckDB)
─────────────         ───────────────────────        ────────────────────────
questions_raw.csv  →  questions_clean.parquet    →   stg_questions
(scraping OpenTDB)    (nettoyage, dedup,              stg_ai_responses
                       melange des choix)              stg_responses_enriched
                                                        │
                       ai_responses.parquet        →    fct_model_performance
                       (reponses LLM brutes,              fct_prompt_performance
                        via enrich.py)                    fct_category_accuracy
                                                           fct_difficulty_accuracy
                                                           fct_response_time
```

- **Bronze** (`data/bronze/`) : dump brut du scraping OpenTDB. `raw_json/`
  contient chaque payload API tel que reçu (traçabilité, non versionné) ;
  `questions_raw.csv` en est l'aplatissement.
- **Silver** (`data/silver/`) : `questions_clean.parquet` (dataset nettoyé et
  dédupliqué) et `ai_responses.parquet` (réponses brutes du/des modèles,
  produites par `enrich.py`).
- **Gold** (`data/gold/benchmark.duckdb`) : construit par dbt à partir de la
  couche silver — répond directement aux questions métier du benchmark
  (performance par modèle, par prompt, par catégorie, par difficulté, par
  temps de réponse).

## Organisation du repo

```
business-intelligence/
  data/
    bronze/            # CSV brut + dumps JSON (raw_json/ non versionne)
    silver/            # parquet nettoye + reponses LLM
    gold/               # benchmark.duckdb (genere par dbt)
  src/
    scraping/           # client OpenTDB + orchestration du scraping
    processing/         # nettoyage bronze -> silver
    llm/                # prompts, client LMStudio, enrichissement
  dbt/benchmark/         # projet dbt-duckdb (staging + marts gold)
  streamlit_app/         # dashboard interactif (6 pages)
  requirements.txt
  .env.example
```

## Méthodologie

### 1. Scraping (bronze)

`src/scraping/scrape_bronze.py` récupère l'intégralité du dataset OpenTDB
(vérifié via `/api_count_global.php` : **5298 questions vérifiées**, toutes
récupérées) en respectant la limite officielle de l'API (1 requête / 5 s /
IP) et un token de session pour ne jamais recevoir deux fois la même
question. Chaque combinaison catégorie × difficulté × type est vidée par une
sonde d'existence (1 appel) puis une phase "bulk" (lots de 50) et une
décomposition binaire du reliquat (< 50), pour minimiser le nombre de
requêtes sous la contrainte du rate-limit.

### 2. Nettoyage (silver)

`src/processing/clean_silver.py` déduplique, génère un `question_id` stable
(hash catégorie + question), et mélange les choix de réponse (bonne +
mauvaises réponses) de façon reproductible. **5295 questions** en sortie
(5298 moins quelques doublons/collisions légitimes côté source OpenTDB).

### 3. Enrichissement LLM

`src/llm/enrich.py` interroge le modèle chargé dans LMStudio (via le SDK
Python officiel `lmstudio`) pour chaque question, avec 3 variantes de prompt
(`src/llm/prompts.py`) :

| Variante | Description |
|---|---|
| `naive` | La question brute, sans aucune consigne de format. |
| `strict_format` | Consigne explicite de répondre uniquement par la réponse, sans phrase. |
| `role_expert` | Rôle "expert de trivia" + catégorie/difficulté en contexte + format strict. |

**Important — échantillonnage** : l'enrichissement se fait sur un
**échantillon stratifié** (catégorie × difficulté) du dataset silver, pas sur
son intégralité. À ~7-90 s par appel selon le modèle, un run exhaustif
(5295 questions × 3 prompts) aurait pris de plusieurs heures à plusieurs
jours selon le modèle — disproportionné pour ce benchmark. L'échantillonnage
stratifié garde des proportions catégorie/difficulté représentatives du
dataset complet.

Pour chaque réponse : `ai_answer` (texte brut, nettoyé du raisonnement interne
du modèle le cas échéant), `ai_correct` (comparaison normalisée — voir
limites), `response_time` (mesuré en secondes autour de l'appel).

Le script écrit un **checkpoint incrémental** (`data/silver/.ai_responses_checkpoint.jsonl`)
: relancer `enrich.py` (même modèle ou un nouveau) reprend là où on s'est
arrêté et **n'écrase jamais** les réponses déjà calculées — utile à la fois
pour la résilience (coupure réseau/serveur) et pour ajouter des modèles à
comparer sans tout relancer.

### 4. Gold (dbt)

Le projet `dbt/benchmark/` (adapter `dbt-duckdb`) matérialise la couche gold
dans `data/gold/benchmark.duckdb`, avec 5 modèles marts, chacun répondant à
une question métier explicite (voir le commentaire en tête de chaque fichier
SQL dans `dbt/benchmark/models/marts/`).

### 5. Dashboard

`streamlit_app/` (6 pages) lit `benchmark.duckdb` en lecture seule et propose
des filtres interactifs (modèle, variante de prompt) sur chaque vue.

## Limites & points d'attention

Documentées ici plutôt que cachées, parce qu'elles sont utiles pour
interpréter les résultats correctement :

- **Grading par inclusion, pas par égalité stricte** : une réponse est
  considérée correcte si la bonne réponse (normalisée) apparaît dans la
  réponse du modèle. Ce choix évite de pénaliser injustement les réponses
  verbeuses mais correctes (ex. prompt `naive`), mais introduit un biais
  inverse : `naive` produisant des phrases plus longues, il a
  mécaniquement plus de chances de "contenir" la bonne réponse. L'écart
  mesuré entre `naive` et `strict_format` n'est donc pas entièrement
  imputable à une différence de qualité de réponse.
- **Questions booléennes** : le prompt est en français, alors qu'OpenTDB
  attend un littéral anglais `True`/`False`. Un filet de sécurité dans le
  grading accepte les équivalents (Oui/Vrai/Yes/True, Non/Faux/No/False),
  et les prompts avec consigne de format demandent explicitement `True`/`False`.
- **Comparaison de modèles asymétrique** : `gemma-3-4b` a un échantillon
  complet (200 questions × 3 prompts = 633 réponses) tandis que
  `gemma-4-12b-qat` est **incomplet** (103/150 réponses — le modèle a été
  déchargé de LMStudio en cours de run, probablement suite à une mise en
  veille de la machine). Le taux de 27,2 % pour le 12B est donc à interpréter
  avec prudence (petit échantillon, biaisé vers les prompts `naive`/`strict_format`,
  quasiment aucune réponse `role_expert`).
- **Matériel** : benchmark exécuté sur CPU (pas de GPU dédié), ce qui explique
  les temps de réponse élevés notamment pour le modèle 12B (~5 tokens/s).
  Un modèle "reasoning" (comme `gemma-4-12b-qat`) consomme une bonne partie
  de son budget de tokens en raisonnement interne avant de répondre.

## Setup complet

### Prérequis

- Python 3.14 (testé) — un venv dédié est recommandé
- [LMStudio](https://lmstudio.ai/) installé, avec au moins un modèle
  instruct téléchargé (ex. `gemma-3-4b`), serveur local démarré
  (onglet **Developer** > sélectionner le modèle > **Start Server**,
  par défaut sur `http://localhost:1234`)

### Installation

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -r requirements.txt
cp .env.example .env
# éditer .env : LMSTUDIO_MODEL=<nom exact tel qu'affiché dans LMStudio>
```

### Exécution du pipeline (dans l'ordre)

```bash
# 1. Bronze : scraping complet d'OpenTDB (~2h, rate-limit oblige)
python src/scraping/scrape_bronze.py

# 2. Silver : nettoyage
python src/processing/clean_silver.py

# 3. Enrichissement LLM (LMStudio doit tourner) : echantillon de 200 questions x 3 prompts
python src/llm/enrich.py --sample-size 200 --model <nom-du-modele>
# ajouter --all pour le dataset complet (long), --sample-size N pour un test rapide

# 4. Gold : dbt
cd dbt/benchmark
DBT_PROFILES_DIR=. dbt run
DBT_PROFILES_DIR=. dbt test
cd ../..

# 5. Dashboard
streamlit run streamlit_app/app.py
```

### Comparer un nouveau modèle

Charger le modèle dans LMStudio, puis relancer l'étape 3 avec
`--model <nouveau-nom>` : les résultats s'ajoutent à `ai_responses.parquet`
sans toucher aux modèles déjà benchmarkés. Relancer ensuite `dbt run
--full-refresh` pour rafraîchir la couche gold, puis le dashboard reflète
automatiquement le nouveau modèle.
