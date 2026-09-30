-- Question metier : quel modele est globalement le plus performant, et le plus rapide ?
select
    model_name,
    count(*) as n_reponses,
    sum(case when ai_correct then 1 else 0 end) as n_correctes,
    round(avg(case when ai_correct then 1.0 else 0.0 end), 4) as taux_reussite,
    round(avg(response_time), 2) as temps_moyen_s,
    round(median(response_time), 2) as temps_median_s
from {{ ref('stg_ai_responses') }}
group by model_name
