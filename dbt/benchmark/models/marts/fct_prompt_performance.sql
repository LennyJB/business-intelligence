-- Question metier : quelle formulation de prompt donne le meilleur taux de reussite,
-- pour chaque modele ?
select
    model_name,
    prompt_variant,
    count(*) as n_reponses,
    round(avg(case when ai_correct then 1.0 else 0.0 end), 4) as taux_reussite,
    round(avg(response_time), 2) as temps_moyen_s
from {{ ref('stg_ai_responses') }}
group by model_name, prompt_variant
