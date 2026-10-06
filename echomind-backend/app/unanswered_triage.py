"""Regras conservadoras para a fila de perguntas não respondidas.

Esta versão é usada pela migration 0020 para classificar registros antigos.
Mudanças futuras de critérios devem criar uma nova versão de classificação.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Literal


TriageStatus = Literal["pending", "review", "discard"]


@dataclass(frozen=True)
class TriageDecision:
    status: TriageStatus
    reason: str | None = None


_ABUSIVE_WORDS = frozenset({
    "arrombada", "arrombadas", "arrombado", "arrombados", "babaca", "babacas",
    "bosta", "burra", "burras", "burro", "burros", "cacete", "carai",
    "caralho", "crl", "cu", "danar", "desgraca", "desgracada", "desgracadas",
    "desgracado", "desgracados", "escrota", "escrotas", "escroto", "escrotos",
    "estupida", "estupidas", "estupido", "estupidos", "fdp", "foda",
    "fodase", "foder", "fodida", "fodidas", "fodido", "fodidos", "idiota",
    "idiotas", "imbecil", "imbecis", "krl", "lixo", "merda", "otaria",
    "otarias", "otario", "otarios", "palhaca", "palhacas", "palhaco",
    "palhacos", "porra", "pqp", "puta", "putas", "puto", "putos",
    "retardada", "retardadas", "retardado", "retardados", "tmnc", "vsf",
    "vtnc", "vagabunda", "vagabundas", "vagabundo", "vagabundos",
})
_ABUSIVE_PHRASES = (
    "cala a boca", "filho da mae", "se lasque", "vai se ferrar",
    "vai se lascar", "vai pro inferno", "vai para o inferno",
)
_FILLER_WORDS = frozenset({
    "a", "as", "da", "de", "do", "e", "filha", "filho", "me", "na",
    "no", "o", "os", "para", "pra", "pro", "que", "se", "seu", "seus",
    "sua", "suas", "te", "tomar", "tu", "vai", "voces", "voce",
})
_NON_QUESTIONS = frozenset({
    "bom dia", "boa tarde", "boa noite", "obrigado", "obrigada", "oi",
    "ola", "teste", "testando", "kkkk", "kkkkk",
})
_OFF_TOPIC_PHRASES = (
    "conte uma piada", "me conte uma piada", "receita de bolo",
    "previsao do tempo", "qual a previsao do tempo",
)
_URL_PATTERN = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_ABUSE_CHAR_TRANSLATION = str.maketrans({
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t",
    "@": "a", "$": "s",
})


def normalized_question(question: str) -> str:
    text = unicodedata.normalize("NFKD", question.casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.findall(r"[^\W_]+", text, flags=re.UNICODE))


def question_fingerprint(question: str) -> str:
    return hashlib.sha256(normalized_question(question).encode("utf-8")).hexdigest()


def _normalized_abuse_text(question: str) -> str:
    text = unicodedata.normalize("NFKD", question.casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.translate(_ABUSE_CHAR_TRANSLATION)
    text = re.sub(r"(?<=[a-z])\*(?=[a-z])", "o", text)
    return " ".join(re.findall(r"[^\W_]+", text, flags=re.UNICODE))


def classify_question_v1(question: str) -> TriageDecision:
    normalized = normalized_question(question)
    words = normalized.split()

    if not words or not any(char.isalpha() for char in normalized):
        return TriageDecision("discard", "no_meaningful_text")
    if normalized in _NON_QUESTIONS:
        return TriageDecision("discard", "non_question")
    if len(words) == 1 and re.fullmatch(r"(.)\1{3,}", words[0]):
        return TriageDecision("discard", "repeated_text")
    if len(words) >= 8 and len(set(words)) <= 2:
        return TriageDecision("discard", "repeated_text")
    if _URL_PATTERN.fullmatch(question.strip()):
        return TriageDecision("discard", "link_only")
    if _URL_PATTERN.search(question):
        return TriageDecision("review", "external_link")
    abuse_text = _normalized_abuse_text(question)
    remaining = f" {abuse_text} "
    phrase_found = False
    for phrase in _ABUSIVE_PHRASES:
        remaining, count = re.subn(rf"(?<!\w){re.escape(phrase)}(?!\w)", " ", remaining)
        phrase_found |= count > 0
    abuse_words = abuse_text.split()
    if phrase_found or any(word in _ABUSIVE_WORDS for word in abuse_words):
        if all(word in _ABUSIVE_WORDS | _FILLER_WORDS for word in remaining.split()):
            return TriageDecision("discard", "abuse_only")
        return TriageDecision("review", "abusive_language")
    if any(phrase in normalized for phrase in _OFF_TOPIC_PHRASES):
        return TriageDecision("review", "possible_off_topic")
    if len(words) == 1:
        return TriageDecision("review", "unclear")
    return TriageDecision("pending")


def classify_group_v1(questions: list[str]) -> TriageDecision:
    """Reclassifica grupos legados considerando também as variações gravadas."""
    decisions = [classify_question_v1(question) for question in questions]
    if decisions and all(decision.status == "discard" for decision in decisions):
        return decisions[0]
    for decision in decisions:
        if decision.status == "review":
            return decision
    if any(decision.status == "discard" for decision in decisions):
        return TriageDecision("review", "mixed_variants")
    return TriageDecision("pending")
