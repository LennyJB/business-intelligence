-- Question metier : sur quelles thematiques (categories OpenTDB) le modele est-il
-- le plus fiable ou le plus en difficulte ?
select
    category,
    model_name,
    prompt_variant,
    count(*) as n_reponses,
    round(avg(case when ai_correct then 1.0 else 0.0 end), 4) as taux_reussite
from {{ ref('stg_responses_enriched') }}
group by category, model_name, prompt_variant
