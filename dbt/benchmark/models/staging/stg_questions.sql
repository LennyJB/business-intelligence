-- Couche staging : questions nettoyees (silver), renommage/typage leger.
select
    question_id,
    category,
    type as question_type,
    difficulty,
    question,
    correct_answer
from {{ source('silver', 'questions_clean') }}
