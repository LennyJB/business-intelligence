"""
Client pour l'API Open Trivia Database (https://opentdb.com).

Gere le rate-limit officiel de l'API (1 requete / 5s / IP), le token de
session (pour eviter les doublons de questions) et le decodage base64
des champs textuels (evite les soucis d'entites HTML de l'encodage par
defaut).
"""

import base64
import time

import requests

BASE_URL = "https://opentdb.com"
MIN_DELAY_SECONDS = 5.1  # marge de securite au dessus des 5s imposees par l'API

DIFFICULTIES = ("easy", "medium", "hard")
QUESTION_TYPES = ("multiple", "boolean")

# Codes de reponse documentes par l'API (champ "response_code")
RC_SUCCESS = 0
RC_NO_RESULTS = 1
RC_INVALID_PARAMETER = 2
RC_TOKEN_NOT_FOUND = 3
RC_TOKEN_EMPTY = 4
RC_RATE_LIMIT = 5


class OpenTDBClient:
    def __init__(self):
        self.session = requests.Session()
        self._last_call = 0.0

    def _wait_for_rate_limit(self):
        elapsed = time.monotonic() - self._last_call
        if elapsed < MIN_DELAY_SECONDS:
            time.sleep(MIN_DELAY_SECONDS - elapsed)

    def _get(self, path, params=None, retries=3):
        for attempt in range(1, retries + 1):
            self._wait_for_rate_limit()
            try:
                resp = self.session.get(f"{BASE_URL}{path}", params=params, timeout=30)
                self._last_call = time.monotonic()
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.RequestException as exc:
                self._last_call = time.monotonic()
                if attempt == retries:
                    raise
                backoff = MIN_DELAY_SECONDS * attempt
                print(f"  (requete echouee: {exc}; nouvel essai dans {backoff:.0f}s)")
                time.sleep(backoff)

    def get_categories(self):
        """Retourne la liste des categories: [{"id": int, "name": str}, ...]."""
        data = self._get("/api_category.php")
        return data["trivia_categories"]

    def request_session_token(self):
        """Demande un nouveau token de session (evite les doublons de questions)."""
        data = self._get("/api_token.php", params={"command": "request"})
        return data["token"]

    def fetch_questions(self, amount, category=None, difficulty=None, qtype=None, token=None):
        """
        Interroge /api.php et retourne (response_code, questions_decodees).

        Reessaie automatiquement une fois en cas de RC_RATE_LIMIT (5),
        au cas ou l'horloge locale et celle du serveur divergeraient.
        """
        params = {"amount": amount, "encode": "base64"}
        if category is not None:
            params["category"] = category
        if difficulty is not None:
            params["difficulty"] = difficulty
        if qtype is not None:
            params["type"] = qtype
        if token is not None:
            params["token"] = token

        data = self._get("/api.php", params=params)
        if data["response_code"] == RC_RATE_LIMIT:
            time.sleep(MIN_DELAY_SECONDS)
            data = self._get("/api.php", params=params)

        questions = [_decode_question(q) for q in data.get("results", [])]
        return data["response_code"], questions


def _b64decode(s):
    return base64.b64decode(s).decode("utf-8")


def _decode_question(raw):
    return {
        "category": _b64decode(raw["category"]),
        "type": _b64decode(raw["type"]),
        "difficulty": _b64decode(raw["difficulty"]),
        "question": _b64decode(raw["question"]),
        "correct_answer": _b64decode(raw["correct_answer"]),
        "incorrect_answers": [_b64decode(a) for a in raw["incorrect_answers"]],
    }
