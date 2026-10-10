"""Exercita receive ASGI real, inclusive corpos sem Content-Length confiavel."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def multipart_body(content, *, metadata=b"", extra_file=False):
    prefix = b'--upload\r\nContent-Disposition: form-data; name="file"; filename="norma.txt"\r\nContent-Type: text/plain\r\n\r\n'
    body = prefix + content + b"\r\n"
    if extra_file:
        body += prefix.replace(b"norma.txt", b"outro.txt") + (
            extra_file if isinstance(extra_file, bytes) else b"outro"
        ) + b"\r\n"
    if metadata:
        fields = metadata if isinstance(metadata, dict) else {"department": metadata}
        for name, value in fields.items():
            body += b'--upload\r\nContent-Disposition: form-data; name="' + name.encode() + b'"\r\n\r\n' + value + b"\r\n"
    return body + b"--upload--\r\n"


async def send_stream(app, body, *, content_length=None, chunk_size=16384, path="/documents/upload", headers=()):
    received = 0
    calls = 0
    sent = []
    wait_for_disconnect = asyncio.Event()

    async def receive():
        nonlocal received, calls
        if received >= len(body):
            await wait_for_disconnect.wait()
            return {"type": "http.disconnect"}
        chunk = body[received:received + chunk_size]
        received += len(chunk)
        calls += 1
        return {"type": "http.request", "body": chunk, "more_body": received < len(body)}

    async def send(message):
        sent.append(message)

    headers = [(b"content-type", b"multipart/form-data; boundary=upload"), *headers]
    if content_length is not None:
        headers.append((b"content-length", content_length))
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "scheme": "http", "path": path, "raw_path": path.encode(),
        "root_path": "", "query_string": b"", "headers": headers,
        "client": ("127.0.0.1", 12345), "server": ("testserver", 80),
    }
    await asyncio.wait_for(app(scope, receive, send), timeout=10)
    return SimpleNamespace(
        status=next(message["status"] for message in sent if message["type"] == "http.response.start"),
        body=b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body"),
        headers=dict(next(message["headers"] for message in sent if message["type"] == "http.response.start")),
        received=received, calls=calls,
    )


@pytest.fixture()
def parser_io(monkeypatch):
    import multipart
    from starlette import formparsers

    files = []
    parsed = []
    create_tempfile = formparsers.SpooledTemporaryFile
    write = multipart.MultipartParser.write

    def tempfile(*args, **kwargs):
        result = create_tempfile(*args, **kwargs)
        files.append(result)
        return result

    def parser_write(parser, data):
        parsed.append(len(data))
        return write(parser, data)

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", tempfile)
    monkeypatch.setattr(multipart.MultipartParser, "write", parser_write)
    return SimpleNamespace(files=files, parsed=parsed)


@pytest.mark.asyncio
@pytest.mark.parametrize("content_length", [None, b"1", b"invalid"])
@pytest.mark.parametrize("chunk_size", [4096, 16384, 65536])
async def test_rejects_excess_before_receiving_or_parsing_entire_body(
    client, quick_test_context, monkeypatch, parser_io, content_length, chunk_size,
):
    from app import main
    from starlette.middleware.cors import CORSMiddleware

    monkeypatch.setenv("MAX_DOCUMENT_SIZE_MB", "1")
    task = SimpleNamespace(calls=0)

    def process(**kwargs):
        task.calls += 1

    monkeypatch.setattr(main, "process_document", process)
    body = multipart_body(b"x" * (4 * 1024 * 1024))
    cors = next(m for m in quick_test_context.app.user_middleware if m.cls is CORSMiddleware)
    origin = cors.kwargs["allow_origins"][0].encode()
    result = await send_stream(
        quick_test_context.app, body, content_length=content_length, chunk_size=chunk_size,
        headers=[(b"origin", origin)],
    )

    assert result.status == 413
    assert result.headers[b"access-control-allow-origin"] == origin
    assert result.received < len(body)
    assert result.received <= 1024 * 1024 + 64 * 1024 + 3 * chunk_size
    assert sum(parser_io.parsed) <= 1024 * 1024 + 64 * 1024
    assert task.calls == 0
    assert parser_io.files
    assert all(file.closed for file in parser_io.files)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "max_mb,offset,content_length", [(1, 0, None), (1, -1, b"1"), (2, 0, b"99999999")],
)
async def test_valid_file_near_configured_limit_with_optional_metadata(
    client, quick_test_context, monkeypatch, parser_io, max_mb, offset, content_length,
):
    from app import main

    monkeypatch.setenv("MAX_DOCUMENT_SIZE_MB", str(max_mb))
    task = MagicMock()
    monkeypatch.setattr(main, "process_document", task)
    content = b"x" * (max_mb * 1024 * 1024 + offset)
    body = multipart_body(content, metadata={
        "document_type": b"regulamento", "document_number": b"42/2026",
        "department": b"Secretaria", "published_at": b"2026-09-01", "valid_until": b"2027-09-01",
    })
    result = await send_stream(quick_test_context.app, body, content_length=content_length)

    assert result.status == 202
    assert result.received == sum(parser_io.parsed) == len(body)
    document = json.loads(result.body)
    assert document["size_bytes"] == len(content)
    assert document["department"] == "Secretaria"
    assert document["document_number"] == "42/2026"
    task.assert_called_once_with(document_id=document["id"], tenant_id="test-admin", content=content)
    assert all(file.closed for file in parser_io.files)
    if max_mb == 2:
        assert all(file._rolled for file in parser_io.files)


@pytest.mark.asyncio
async def test_file_size_still_rejected_inside_the_multipart_envelope_allowance(
    client, quick_test_context, monkeypatch, parser_io,
):
    monkeypatch.setenv("MAX_DOCUMENT_SIZE_MB", "1")
    body = multipart_body(b"x" * (1024 * 1024 + 1))
    result = await send_stream(quick_test_context.app, body)

    assert result.status == 413
    assert result.received == len(body) < 1024 * 1024 + 64 * 1024
    assert all(file.closed and file._rolled for file in parser_io.files)


@pytest.mark.asyncio
async def test_envelope_cannot_add_unbounded_metadata_to_a_maximum_size_file(
    client, quick_test_context, monkeypatch, parser_io,
):
    monkeypatch.setenv("MAX_DOCUMENT_SIZE_MB", "1")
    body = multipart_body(b"x" * (1024 * 1024), metadata=b"m" * (256 * 1024))
    result = await send_stream(quick_test_context.app, body)

    assert result.status == 413
    assert result.received < len(body)
    assert sum(parser_io.parsed) <= 1024 * 1024 + 64 * 1024
    assert all(file.closed for file in parser_io.files)


@pytest.mark.asyncio
@pytest.mark.parametrize("extra_file", [True, b"x" * (4 * 1024 * 1024)], ids=["small", "large"])
async def test_multiple_files_reject_and_close_temporaries_before_large_second_file(
    client, quick_test_context, monkeypatch, parser_io, extra_file,
):
    monkeypatch.setenv("MAX_DOCUMENT_SIZE_MB", "1")
    body = multipart_body(b"primeiro", extra_file=extra_file)
    result = await send_stream(quick_test_context.app, body)

    assert result.status == 400
    assert json.loads(result.body) == {"detail": "Envie exatamente um arquivo por requisição."}
    assert len(parser_io.files) == 1
    assert parser_io.files[0].closed
    if isinstance(extra_file, bytes):
        assert result.received < len(body)


@pytest.mark.asyncio
async def test_malformed_multipart_closes_already_created_file(
    client, quick_test_context, monkeypatch, parser_io,
):
    monkeypatch.setenv("MAX_DOCUMENT_SIZE_MB", "2")
    body = multipart_body(b"x" * (1024 * 1024 + 65536)).replace(
        b"--upload--\r\n", b"--upload\r\ninvalid header\r\n\r\n",
    )
    result = await send_stream(quick_test_context.app, body)

    assert result.status == 400
    assert parser_io.files and all(file.closed and file._rolled for file in parser_io.files)


@pytest.mark.asyncio
@pytest.mark.parametrize("configured_limit", ["0", "invalid"])
async def test_invalid_limit_fails_before_receiving_body(
    client, quick_test_context, monkeypatch, parser_io, configured_limit,
):
    monkeypatch.setenv("MAX_DOCUMENT_SIZE_MB", configured_limit)
    result = await send_stream(quick_test_context.app, multipart_body(b"x" * (2 * 1024 * 1024)))

    assert result.status == 500
    assert json.loads(result.body) == {"detail": "Configuração inválida do limite de upload."}
    assert result.received == 0
    assert parser_io.parsed == parser_io.files == []


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", [
    {"type": "lifespan"},
    {"type": "http", "method": "POST", "path": "/chat"},
    {"type": "http", "method": "GET", "path": "/documents/upload"},
])
async def test_barrier_is_exclusive_to_document_upload(monkeypatch, scope):
    from app.document_upload import DocumentUploadLimitMiddleware
    from unittest.mock import AsyncMock

    monkeypatch.setenv("MAX_DOCUMENT_SIZE_MB", "invalid")
    inner = AsyncMock()
    receive, send = AsyncMock(), AsyncMock()
    await DocumentUploadLimitMiddleware(inner)(scope, receive, send)
    inner.assert_awaited_once_with(scope, receive, send)
    receive.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,status", [("auth", 403), ("metadata", 422), ("persistence", 500)])
async def test_upload_failures_close_files_and_do_not_schedule_processing(
    client, quick_test_context, monkeypatch, parser_io, failure, status,
):
    from app import main

    monkeypatch.setenv("MAX_DOCUMENT_SIZE_MB", "2")
    task = MagicMock()
    monkeypatch.setattr(main, "process_document", task)
    if failure == "auth":
        monkeypatch.delitem(quick_test_context.app.dependency_overrides, quick_test_context.get_current_user)
    if failure == "persistence":
        monkeypatch.setattr(main, "create_document", MagicMock(side_effect=RuntimeError("falha sintetica")))
    body = multipart_body(
        b"x" * (1024 * 1024 + 65536),
        metadata={"published_at": b"invalid"} if failure == "metadata" else b"",
    )
    result = await send_stream(quick_test_context.app, body)

    assert result.status == status
    task.assert_not_called()
    assert parser_io.files and all(file.closed and file._rolled for file in parser_io.files)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["disconnect", "cancel"])
async def test_interrupted_receive_closes_the_partial_temporary_file(
    quick_test_context, parser_io, failure,
):
    from fastapi import HTTPException, Request

    handler = next(route for route in quick_test_context.app.routes if route.path == "/documents/upload").get_route_handler()
    body = multipart_body(b"x" * (2 * 1024 * 1024))
    calls = 0

    async def receive():
        nonlocal calls
        calls += 1
        if calls == 3:
            if failure == "cancel":
                raise asyncio.CancelledError()
            return {"type": "http.disconnect"}
        return {"type": "http.request", "body": body[(calls - 1) * 700000:calls * 700000], "more_body": True}

    request = Request({"type": "http", "headers": [(b"content-type", b"multipart/form-data; boundary=upload")]}, receive)
    if failure == "cancel":
        with pytest.raises(asyncio.CancelledError):
            await handler(request)
    else:
        with pytest.raises(HTTPException) as error:
            await handler(request)
        assert error.value.status_code == 400
    assert parser_io.files and all(file.closed and file._rolled for file in parser_io.files)
