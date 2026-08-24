"""Contratos unitarios da fronteira de validacao documental."""

from __future__ import annotations

from io import BytesIO

import pytest
from docx import Document


@pytest.fixture()
def ingestion():
    from app import document_ingestion

    return document_ingestion


@pytest.fixture()
def synthetic_docx_bytes():
    """Cria DOCX minimo em memoria, sem dados reais ou acesso de rede."""

    def build(*, paragraphs: list[tuple[str, str | None]], table_rows=None) -> bytes:
        document = Document()
        for text, style in paragraphs:
            document.add_paragraph(text, style=style)
        if table_rows is not None:
            table = document.add_table(rows=0, cols=len(table_rows[0]))
            for row_values in table_rows:
                cells = table.add_row().cells
                for cell, value in zip(cells, row_values, strict=True):
                    cell.text = value
        output = BytesIO()
        document.save(output)
        return output.getvalue()

    return build


@pytest.mark.parametrize(
    ("filename", "mime_type"),
    [
        ("regulamento.pdf", "application/pdf"),
        ("notas.TXT", "text/plain; charset=utf-8"),
        (
            "ata.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
    ],
)
def test_allowed_extension_and_matching_mime_are_accepted(
    ingestion, filename, mime_type
) -> None:
    document = ingestion.validate_document_bytes(
        filename=filename,
        mime_type=mime_type,
        content=b"conteudo original",
        max_size_bytes=100,
    )

    assert document.filename == filename
    assert document.mime_type == mime_type.split(";", maxsplit=1)[0].lower()


@pytest.mark.parametrize(
    ("filename", "mime_type", "error_name"),
    [
        ("arquivo.exe", "application/octet-stream", "UnsupportedDocumentTypeError"),
        ("arquivo.pdf", "text/plain", "InvalidDocumentMimeTypeError"),
        ("arquivo.txt", "application/pdf", "InvalidDocumentMimeTypeError"),
        ("arquivo.docx", None, "InvalidDocumentMimeTypeError"),
    ],
)
def test_invalid_extension_or_mime_combination_is_rejected(
    ingestion, filename, mime_type, error_name
) -> None:
    with pytest.raises(getattr(ingestion, error_name)):
        ingestion.validate_document_bytes(
            filename=filename,
            mime_type=mime_type,
            content=b"conteudo original",
            max_size_bytes=100,
        )


def test_empty_document_is_rejected(ingestion) -> None:
    with pytest.raises(ingestion.EmptyDocumentError):
        ingestion.validate_document_bytes(
            filename="vazio.txt",
            mime_type="text/plain",
            content=b"",
            max_size_bytes=1,
        )


def test_document_at_limit_is_accepted_and_above_limit_is_rejected(ingestion) -> None:
    accepted = ingestion.validate_document_bytes(
        filename="limite.txt",
        mime_type="text/plain",
        content=b"12345",
        max_size_bytes=5,
    )

    assert accepted.size_bytes == 5
    with pytest.raises(ingestion.DocumentTooLargeError):
        ingestion.validate_document_bytes(
            filename="excesso.txt",
            mime_type="text/plain",
            content=b"123456",
            max_size_bytes=5,
        )


def test_max_document_size_is_configurable(monkeypatch, ingestion) -> None:
    monkeypatch.setenv("MAX_DOCUMENT_SIZE_MB", "2")

    assert ingestion.get_max_document_size_bytes() == 2 * 1024 * 1024
    with pytest.raises(ingestion.InvalidDocumentConfigurationError):
        ingestion.get_max_document_size_bytes("zero")


def test_stream_is_read_only_until_the_first_byte_over_the_limit(ingestion) -> None:
    source = BytesIO(b"123456")

    with pytest.raises(ingestion.DocumentTooLargeError):
        ingestion.read_limited_bytes(source, max_size_bytes=5, chunk_size=2)

    assert source.tell() == 6


def test_sha256_is_deterministic_and_sensitive_to_original_bytes(ingestion) -> None:
    first = ingestion.validate_document_bytes(
        filename="original.txt",
        mime_type="text/plain",
        content=b"linha 1\r\nlinha 2",
        max_size_bytes=100,
    )
    same_bytes = ingestion.validate_document_bytes(
        filename="outro-nome.txt",
        mime_type="text/plain",
        content=b"linha 1\r\nlinha 2",
        max_size_bytes=100,
    )
    changed_bytes = ingestion.validate_document_bytes(
        filename="normalizado.txt",
        mime_type="text/plain",
        content=b"linha 1\nlinha 2",
        max_size_bytes=100,
    )

    assert first.sha256 == same_bytes.sha256
    assert first.sha256 != changed_bytes.sha256


@pytest.mark.parametrize(
    ("raw_filename", "expected_filename"),
    [
        ("../../segredo.txt", "segredo.txt"),
        (r"C:\upload\relatorio.pdf", "relatorio.pdf"),
        ("  pasta/ata\x00.docx  ", "ata.docx"),
    ],
)
def test_filename_is_sanitized_to_a_safe_basename(
    ingestion, raw_filename, expected_filename
) -> None:
    assert ingestion.sanitize_filename(raw_filename) == expected_filename


@pytest.mark.parametrize("filename", ["", ".", "..", "../"])
def test_filename_without_safe_basename_is_rejected(ingestion, filename) -> None:
    with pytest.raises(ingestion.InvalidDocumentFilenameError):
        ingestion.sanitize_filename(filename)


@pytest.mark.parametrize("status", ["pending", "processing", "ready"])
def test_active_duplicate_is_rejected_only_inside_the_same_tenant(
    db, ingestion, status
) -> None:
    from app import document_repository

    content = b"mesmo conteudo"
    sha256 = ingestion.validate_document_bytes(
        filename="original.txt",
        mime_type="text/plain",
        content=content,
        max_size_bytes=100,
    ).sha256
    existing_document = document_repository.create_document(
        db,
        tenant_id="tenant-a",
        data=document_repository.DocumentCreateData(
            filename="original.txt",
            mime_type="text/plain",
            size_bytes=len(content),
            sha256=sha256,
        ),
    )
    if status in {"processing", "ready"}:
        document_repository.transition_document_status(
            db,
            tenant_id="tenant-a",
            document_id=existing_document.id,
            target_status="processing",
        )
    if status == "ready":
        document_repository.transition_document_status(
            db,
            tenant_id="tenant-a",
            document_id=existing_document.id,
            target_status="ready",
        )

    with pytest.raises(document_repository.DuplicateDocumentError):
        ingestion.validate_document_for_tenant(
            db,
            tenant_id="tenant-a",
            filename="copia.txt",
            mime_type="text/plain",
            content=content,
            max_size_bytes=100,
        )

    other_tenant_document = ingestion.validate_document_for_tenant(
        db,
        tenant_id="tenant-b",
        filename="copia.txt",
        mime_type="text/plain",
        content=content,
        max_size_bytes=100,
    )

    assert other_tenant_document.sha256 == sha256


def test_extract_txt_uses_utf8_and_preserves_paragraph_breaks(ingestion) -> None:
    extracted = ingestion.extract_txt("Titulo\r\n\r\nParagrafo dois\rFim".encode())

    assert extracted.blocks == (
        ingestion.ExtractedTextBlock(text="Titulo\n\nParagrafo dois\nFim"),
    )
    assert extracted.text == "Titulo\n\nParagrafo dois\nFim"


def test_extract_txt_uses_documented_cp1252_fallback(ingestion) -> None:
    extracted = ingestion.extract_txt(b"Institui\xe7\xe3o")

    assert extracted.blocks[0].text == "Instituição"


@pytest.mark.parametrize("content", [b"", b" \r\n\t", b"texto\x00binario", b"\x81"])
def test_extract_txt_rejects_empty_or_invalid_content(ingestion, content) -> None:
    expected_error = (
        ingestion.EmptyExtractedDocumentError if content in {b"", b" \r\n\t"}
        else (ingestion.InvalidTextEncodingError if content == b"\x81" else ingestion.InvalidDocumentContentError)
    )

    with pytest.raises(expected_error):
        ingestion.extract_txt(content)


def test_extract_docx_paragraphs_are_ordered_and_headings_define_section(
    ingestion, synthetic_docx_bytes
) -> None:
    content = synthetic_docx_bytes(
        paragraphs=[("Regulamento", "Heading 1"), ("Artigo primeiro", None)],
    )

    extracted = ingestion.extract_docx(content)

    assert extracted.blocks == (
        ingestion.ExtractedTextBlock(text="Regulamento"),
        ingestion.ExtractedTextBlock(text="Artigo primeiro", section="Regulamento"),
    )


def test_extract_docx_table_cells_are_ordered_without_evident_duplicates(
    ingestion, synthetic_docx_bytes
) -> None:
    content = synthetic_docx_bytes(
        paragraphs=[],
        table_rows=[("Campo", "Valor"), ("Campus", "Centro")],
    )

    extracted = ingestion.extract_docx(content)

    assert extracted.blocks == (
        ingestion.ExtractedTextBlock(text="Campo\tValor\nCampus\tCentro"),
    )


def test_extract_docx_does_not_repeat_horizontally_merged_cells(ingestion) -> None:
    document = Document()
    table = document.add_table(rows=2, cols=2)
    merged = table.cell(0, 0).merge(table.cell(0, 1))
    merged.text = "Cabecalho unido"
    table.cell(1, 0).text = "Esquerda"
    table.cell(1, 1).text = "Direita"
    output = BytesIO()
    document.save(output)

    extracted = ingestion.extract_docx(output.getvalue())

    assert extracted.blocks[0].text == "Cabecalho unido\nEsquerda\tDireita"


def test_extract_docx_preserves_order_between_paragraphs_and_table(ingestion) -> None:
    document = Document()
    document.add_paragraph("Antes")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Meio A"
    table.cell(0, 1).text = "Meio B"
    document.add_paragraph("Depois")
    output = BytesIO()
    document.save(output)

    extracted = ingestion.extract_docx(output.getvalue())

    assert [block.text for block in extracted.blocks] == [
        "Antes",
        "Meio A\tMeio B",
        "Depois",
    ]


@pytest.mark.parametrize("content", [b"", b"nao e um docx"])
def test_extract_docx_rejects_empty_or_invalid_content(ingestion, content) -> None:
    with pytest.raises(
        (ingestion.EmptyExtractedDocumentError, ingestion.InvalidDocumentContentError)
    ):
        ingestion.extract_docx(content)


def test_extract_docx_without_text_is_rejected(ingestion, synthetic_docx_bytes) -> None:
    content = synthetic_docx_bytes(paragraphs=[])

    with pytest.raises(ingestion.EmptyExtractedDocumentError):
        ingestion.extract_docx(content)
