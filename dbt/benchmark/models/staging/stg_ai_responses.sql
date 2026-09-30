-- Couche staging : reponses brutes du/des modeles LLM (silver).
select
    question_id,
    model_name,
    prompt_variant,
    ai_answer,
    ai_correct,
    response_time
from {{ source('silver', 'ai_responses') }}
