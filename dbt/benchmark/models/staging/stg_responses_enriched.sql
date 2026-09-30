-- Reponses jointes aux metadonnees de la question (categorie, difficulte, type).
-- Base commune reutilisee par les marts pour eviter de repeter le join.
select
    r.question_id,
    r.model_name,
    r.prompt_variant,
    r.ai_answer,
    r.ai_correct,
    r.response_time,
    q.category,
    q.question_type,
    q.difficulty
from {{ ref('stg_ai_responses') }} r
inner join {{ ref('stg_questions') }} q using (question_id)
