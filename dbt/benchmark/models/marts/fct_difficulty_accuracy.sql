-- Question metier : la precision du modele se degrade-t-elle avec la difficulte
-- annoncee par OpenTDB (easy/medium/hard) ?
select
    difficulty,
    model_name,
    prompt_variant,
    count(*) as n_reponses,
    round(avg(case when ai_correct then 1.0 else 0.0 end), 4) as taux_reussite
from {{ ref('stg_responses_enriched') }}
group by difficulty, model_name, prompt_variant
