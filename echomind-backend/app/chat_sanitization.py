"""Best-effort minimization of common identifiers in new public questions.

This is not anonymization or a prompt-injection/XSS defense. Keep the request
length limit and do not log the original input, including on rejection.
"""

import re
import unicodedata


REDACTED = "[DADO]"
_EMAIL = re.compile(r"(?<![\w.+-])[\w.!#$%&'*+/=?^`{|}~-]+@[\w-]+(?:\.[\w-]+)+(?![\w-])")
_CNPJ = re.compile(r"(?<!\w)(?:[0-9]{2}\.[0-9]{3}\.[0-9]{3}/[0-9]{4}-[0-9]{2}|[0-9]{14})(?!\w)")
_CPF = re.compile(r"(?<!\w)(?:[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}|[0-9]{11})(?!\w)")
_PHONE = re.compile(r"(?<!\w)(?:\+?55[ .-]?)?(?:\([1-9][0-9]\)[ .-]?|[1-9][0-9][ .-]?)[0-9]{4,5}[ .-]?[0-9]{4}(?!\w)")


def sanitize_public_question(message: str) -> str:
    """Return only the minimized question, or reject without echoing its input."""
    if len(message) > 2000:
        raise ValueError("Envie uma pergunta com até 2000 caracteres.")
    normalized = unicodedata.normalize("NFKC", message)
    if len(normalized) > 2000:
        raise ValueError("Envie uma pergunta com até 2000 caracteres.")
    # Join invisible format/control characters embedded in identifiers, while
    # retaining word boundaries for ordinary whitespace and line breaks.
    normalized = "".join(
        char for char in normalized
        if char.isspace() or unicodedata.category(char) not in {"Cc", "Cf", "Cs"}
    )
    question = " ".join(normalized.split())
    for pattern in (_EMAIL, _CNPJ, _PHONE, _CPF):
        question = pattern.sub(REDACTED, question)
    if not any(char.isalnum() for char in question.replace(REDACTED, "")):
        raise ValueError("Envie uma dúvida geral, sem dados pessoais.")
    if len(question) > 2000:
        raise ValueError("Envie uma pergunta com até 2000 caracteres.")
    return question
