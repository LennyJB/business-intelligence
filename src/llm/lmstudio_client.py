"""
Wrapper autour du SDK Python officiel de LMStudio (`lmstudio`).

LMStudio doit tourner en local avec un modele charge et le serveur demarre
(onglet Developer > Start Server). Le SDK se connecte au serveur par
defaut (localhost) sans configuration supplementaire.
"""

import re
import time

import lmstudio as lms

# max_tokens genereux : certains modeles (ex. modeles "reasoning") consomment
# une bonne partie du budget en raisonnement interne avant la reponse finale.
DEFAULT_MAX_TOKENS = 400
DEFAULT_TEMPERATURE = 0.0

# Pour certains modeles "reasoning" (ex. Gemma reasoning), le SDK `lmstudio`
# ne separe pas toujours reasoning_content de content : les deux se
# retrouvent concatenes dans `content`, avec ce marqueur interne entre les
# deux. On ne garde que ce qui suit le marqueur (la reponse finale).
_REASONING_MARKER_RE = re.compile(
    r".*__LM_STUDIO_INTERNAL_LSEP_SYNTHETIC_REASONING_END_[0-9a-f]+__", re.DOTALL
)


def _strip_reasoning(content):
    return _REASONING_MARKER_RE.sub("", content).strip()


class LMStudioClient:
    def __init__(self, model_name, max_tokens=DEFAULT_MAX_TOKENS, temperature=DEFAULT_TEMPERATURE):
        self.model_name = model_name
        self.model = lms.llm(model_name)
        self.config = {"maxTokens": max_tokens, "temperature": temperature}

    def ask(self, prompt):
        """Envoie le prompt au modele et retourne (reponse_texte, temps_ecoule_s)."""
        start = time.perf_counter()
        result = self.model.respond(prompt, config=self.config)
        elapsed = time.perf_counter() - start
        return _strip_reasoning(result.content), elapsed
