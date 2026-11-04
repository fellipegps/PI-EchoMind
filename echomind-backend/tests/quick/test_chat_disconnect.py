"""Disconnection must cancel while waiting for a model, not on the next token."""
import asyncio
from unittest.mock import patch

import pytest

from app.chat_streaming import ChatStreamingResponse
from app.database import Interaction, UnansweredQuestion
from app.middleware import RequestLogMiddleware, TimingMiddleware


def scope(version="2.4"):
    return {"type": "http", "asgi": {"version": "3.0", "spec_version": version},
            "method": "POST", "path": "/chat", "headers": []}


@pytest.mark.parametrize("version", ["2.0", "2.4"])
async def test_disconnect_cancels_awaiting_generator_through_real_middlewares(version):
    disconnect = asyncio.Event()
    finalized = asyncio.Event()
    finished = False
    messages = []

    async def body():
        nonlocal finished
        try:
            yield b"first"
            await asyncio.sleep(30)
            finished = True
            yield b"last"
        finally:
            finalized.set()

    async def receive():
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)
        if message["type"] == "http.response.body" and message.get("body"):
            disconnect.set()

    app = RequestLogMiddleware(TimingMiddleware(ChatStreamingResponse(body())))
    request_scope = scope(version)
    await asyncio.wait_for(app(request_scope, receive, send), timeout=2)
    assert finalized.is_set() and not finished
    assert request_scope["asgi"]["spec_version"] == version
    assert b"".join(message.get("body", b"") for message in messages) == b"first"
    assert messages[0]["headers"] and dict(messages[0]["headers"])[b"cache-control"] == b"no-store"


async def test_send_failure_closes_generator_suspended_at_yield():
    finalized = False

    async def body():
        nonlocal finalized
        try:
            yield b"first"
            await asyncio.sleep(30)
        finally:
            finalized = True

    async def receive():
        await asyncio.Event().wait()

    async def send(message):
        if message["type"] == "http.response.body":
            raise OSError("Synthetic peer closed")

    await asyncio.wait_for(ChatStreamingResponse(body())(scope(), receive, send), timeout=2)
    assert finalized


async def test_completed_stream_preserves_all_chunks_and_background_task():
    from starlette.background import BackgroundTask

    completed = []
    messages = []

    async def body():
        yield "first"
        yield "last"

    async def receive():
        await asyncio.Event().wait()

    async def send(message):
        messages.append(message)

    response = ChatStreamingResponse(body(), background=BackgroundTask(completed.append, "done"))
    await asyncio.wait_for(response(scope(), receive, send), timeout=2)
    assert b"".join(message.get("body", b"") for message in messages) == b"firstlast"
    assert messages[-1]["more_body"] is False
    assert completed == ["done"]


@pytest.mark.parametrize("event_stream", [False, True])
async def test_cancelled_public_chat_saves_partial_history_without_handoff(client, db, fake_rag_engine, event_stream):
    from app.main import _stream_chat_for_tenant

    stopped = asyncio.Event()
    disconnect = asyncio.Event()
    messages = []

    async def slow_answer(question):
        fake_rag_engine.last_had_docs = False
        try:
            yield "Resposta parcial"
            await asyncio.sleep(30)
            yield "Não tenho essa informação."
        finally:
            stopped.set()

    async def receive():
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)
        if message["type"] == "http.response.body":
            disconnect.set()

    with patch.object(fake_rag_engine, "astream_chat", side_effect=slow_answer), patch("app.main._register_unanswered_standalone") as automatic:
        response = await _stream_chat_for_tenant(message="Pergunta sintética", tenant_id="test-admin", db=db,
                                                public_handoff=True, event_stream=event_stream)
        await asyncio.wait_for(response(scope(), receive, send), timeout=2)
    assert stopped.is_set()
    row = db.query(Interaction).one()
    assert row.answer == "Resposta parcial" and not row.was_answered
    assert row.unanswered_token_hash is None and row.unanswered_submitted_at is None
    assert db.query(UnansweredQuestion).count() == 0
    automatic.assert_not_called()
    assert b"event: done" not in b"".join(message.get("body", b"") for message in messages)
