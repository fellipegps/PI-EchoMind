"""Primitivas puras para a fronteira de upload documental.

Este modulo nao extrai conteudo, persiste documentos ou conhece FastAPI. Ele
somente valida os bytes originais que uma futura camada de transporte entregar.
"""

from __future__ import annotations

import hashlib
import os
import posixpath
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, BinaryIO

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


DEFAULT_MAX_DOCUMENT_SIZE_MB = 10
BYTES_PER_MEGABYTE = 1024 * 1024
READ_CHUNK_SIZE = 64 * 1024

ALLOWED_DOCUMENT_MIME_TYPES: dict[str, frozenset[str]] = {
    ".pdf": frozenset({"application/pdf"}),
    ".txt": frozenset({"text/plain"}),
    ".docx": frozenset(
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    ),
}


class DocumentValidationError(Exception):
    """Erro de dominio previsivel na validacao de um upload documental."""


class InvalidDocumentConfigurationError(DocumentValidationError):
    """A configuracao de tamanho maximo nao e valida."""


class InvalidDocumentFilenameError(DocumentValidationError):
    """O nome do arquivo nao produz um basename seguro."""


class UnsupportedDocumentTypeError(DocumentValidationError):
    """A extensao do arquivo nao pertence a allowlist documental."""


class InvalidDocumentMimeTypeError(DocumentValidationError):
    """O MIME informado nao e compativel com a extensao permitida."""


class EmptyDocumentError(DocumentValidationError):
    """O arquivo nao possui bytes para processamento."""


class DocumentTooLargeError(DocumentValidationError):
    """O arquivo excede o tamanho maximo configurado."""


@dataclass(frozen=True, slots=True)
class ValidatedDocument:
    """Metadados derivados de bytes originais ja validados."""

    filename: str
    mime_type: str
    size_bytes: int
    sha256: str


def get_max_document_size_bytes(value: str | None = None) -> int:
    """Retorna o limite configurado por ``MAX_DOCUMENT_SIZE_MB`` em bytes.

    ``value`` existe para testes e para futuras camadas de configuracao; quando
    omitido, a variavel de ambiente do backend e consultada no momento da
    validacao, sem congelar a configuracao durante a importacao do modulo.
    """

    configured_value = os.getenv("MAX_DOCUMENT_SIZE_MB") if value is None else value
    if configured_value is None or not configured_value.strip():
        megabytes = DEFAULT_MAX_DOCUMENT_SIZE_MB
    else:
        try:
            megabytes = int(configured_value)
        except ValueError as exc:
            raise InvalidDocumentConfigurationError(
                "MAX_DOCUMENT_SIZE_MB deve ser um inteiro positivo."
            ) from exc

    if megabytes <= 0:
        raise InvalidDocumentConfigurationError(
            "MAX_DOCUMENT_SIZE_MB deve ser um inteiro positivo."
        )
    return megabytes * BYTES_PER_MEGABYTE


def sanitize_filename(filename: str) -> str:
    """Normaliza um nome para basename seguro, sem caminhos ou caracteres NUL."""

    if not isinstance(filename, str):
        raise InvalidDocumentFilenameError("O nome do arquivo deve ser texto.")

    normalized = unicodedata.normalize("NFC", filename).replace("\x00", "")
    basename = posixpath.basename(normalized.replace("\\", "/")).strip()
    if basename in {"", ".", ".."}:
        raise InvalidDocumentFilenameError("O nome do arquivo nao e valido.")
    if "/" in basename or "\\" in basename or "\x00" in basename:
        raise InvalidDocumentFilenameError("O nome do arquivo nao e seguro.")
    return basename


def normalize_mime_type(mime_type: str | None) -> str:
    """Remove parametros do Content-Type e devolve somente o media type."""

    if not isinstance(mime_type, str):
        raise InvalidDocumentMimeTypeError("O MIME do arquivo deve ser informado.")
    normalized = mime_type.split(";", maxsplit=1)[0].strip().lower()
    if not normalized:
        raise InvalidDocumentMimeTypeError("O MIME do arquivo deve ser informado.")
    return normalized


def validate_document_metadata(filename: str, mime_type: str | None) -> tuple[str, str]:
    """Valida a allowlist dupla: extensao do basename e MIME compativel."""

    safe_filename = sanitize_filename(filename)
    extension = os.path.splitext(safe_filename)[1].lower()
    allowed_mime_types = ALLOWED_DOCUMENT_MIME_TYPES.get(extension)
    if allowed_mime_types is None:
        raise UnsupportedDocumentTypeError("Extensao documental nao permitida.")

    normalized_mime_type = normalize_mime_type(mime_type)
    if normalized_mime_type not in allowed_mime_types:
        raise InvalidDocumentMimeTypeError(
            "O MIME informado nao corresponde a extensao do documento."
        )
    return safe_filename, normalized_mime_type


def read_limited_bytes(
    source: BinaryIO,
    *,
    max_size_bytes: int,
    chunk_size: int = READ_CHUNK_SIZE,
) -> bytes:
    """Le no maximo o limite configurado mais um byte para detectar excesso."""

    if max_size_bytes <= 0 or chunk_size <= 0:
        raise ValueError("max_size_bytes e chunk_size devem ser positivos.")

    chunks: list[bytes] = []
    total_size = 0
    while total_size <= max_size_bytes:
        remaining = max_size_bytes + 1 - total_size
        chunk = source.read(min(chunk_size, remaining))
        if not chunk:
            break
        if not isinstance(chunk, bytes):
            raise TypeError("A fonte de upload deve fornecer bytes.")
        chunks.append(chunk)
        total_size += len(chunk)

    if total_size > max_size_bytes:
        raise DocumentTooLargeError("O arquivo excede o tamanho maximo permitido.")
    return b"".join(chunks)


def validate_document_bytes(
    *,
    filename: str,
    mime_type: str | None,
    content: bytes,
    max_size_bytes: int | None = None,
) -> ValidatedDocument:
    """Valida bytes originais e calcula seu SHA-256 deterministico."""

    if not isinstance(content, bytes):
        raise TypeError("O conteudo do documento deve ser bytes.")

    safe_filename, normalized_mime_type = validate_document_metadata(filename, mime_type)
    size_bytes = len(content)
    if size_bytes == 0:
        raise EmptyDocumentError("Arquivos vazios nao sao permitidos.")

    effective_max_size = (
        get_max_document_size_bytes() if max_size_bytes is None else max_size_bytes
    )
    if effective_max_size <= 0:
        raise InvalidDocumentConfigurationError(
            "O tamanho maximo do documento deve ser positivo."
        )
    if size_bytes > effective_max_size:
        raise DocumentTooLargeError("O arquivo excede o tamanho maximo permitido.")

    return ValidatedDocument(
        filename=safe_filename,
        mime_type=normalized_mime_type,
        size_bytes=size_bytes,
        sha256=hashlib.sha256(content).hexdigest(),
    )


def validate_document_stream(
    *,
    filename: str,
    mime_type: str | None,
    source: BinaryIO,
    max_size_bytes: int | None = None,
) -> ValidatedDocument:
    """Valida uma fonte binaria lendo-a de forma limitada."""

    effective_max_size = (
        get_max_document_size_bytes() if max_size_bytes is None else max_size_bytes
    )
    content = read_limited_bytes(source, max_size_bytes=effective_max_size)
    return validate_document_bytes(
        filename=filename,
        mime_type=mime_type,
        content=content,
        max_size_bytes=effective_max_size,
    )


def validate_document_for_tenant(
    db: "Session",
    *,
    tenant_id: str,
    filename: str,
    mime_type: str | None,
    content: bytes,
    max_size_bytes: int | None = None,
) -> ValidatedDocument:
    """Valida upload e rejeita SHA-256 ativo apenas dentro do tenant informado."""

    # A dependencia de persistencia fica nesta fronteira para que as funcoes de
    # nome, MIME, tamanho e hash continuem importaveis e puras isoladamente.
    from .document_repository import (
        DuplicateDocumentError,
        find_active_duplicate_document,
    )

    document = validate_document_bytes(
        filename=filename,
        mime_type=mime_type,
        content=content,
        max_size_bytes=max_size_bytes,
    )
    duplicate = find_active_duplicate_document(
        db,
        tenant_id=tenant_id,
        sha256=document.sha256,
    )
    if duplicate is not None:
        raise DuplicateDocumentError("Documento ativo com o mesmo SHA-256 neste tenant.")
    return document
