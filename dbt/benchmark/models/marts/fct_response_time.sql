-- Question metier : quelle est la distribution des temps de reponse (rapidite),
-- par modele et par variante de prompt ?
select
    model_name,
    prompt_variant,
    round(min(response_time), 2) as temps_min_s,
    round(avg(response_time), 2) as temps_moyen_s,
    round(median(response_time), 2) as temps_median_s,
    round(max(response_time), 2) as temps_max_s
from {{ ref('stg_ai_responses') }}
group by model_name, prompt_variant
