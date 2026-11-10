"""Disposable HTTPS test adapter. NEVER included in either production image.

Uses the real app, CORS, upload parser/limits and rate limiter, replacing only
external services/document persistence and the generated chat content.
"""

import asyncio
from types import SimpleNamespace

from fastapi import Depends, File, HTTPException, Request, UploadFile

from app import main
from app.database import get_db
from app.document_ingestion import DocumentTooLargeError, get_max_document_size_bytes, read_limited_bytes
from app.document_upload import DocumentUploadRoute
from app.campus_photo import MAX_PHOTO_BYTES
from app.rate_limit import enforce_chat_rate_limit


app = main.app
app.dependency_overrides[get_db] = lambda: None
stream_state = {"completed": 0, "cancelled": 0}


async def synthetic_chat(*, message, **_kwargs):
    async def generate():
        completed = False
        try:
            yield b"first\n"
            await asyncio.sleep(30 if message == "disconnect" else 2)
            yield b"last\n"
            completed = True
            stream_state["completed"] += 1
        finally:
            if not completed:
                stream_state["cancelled"] += 1
    # Exercise the production chat response, including its disconnect listener.
    return main.StreamingResponse(generate(), media_type="text/plain")


main._stream_chat_for_tenant = synthetic_chat
# O portal público resolve a instituição pelo slug; nenhum banco real é usado.
main._public_config_or_404 = lambda _db, _slug: SimpleNamespace(tenant_id="synthetic", privacy_ready=True)


@app.get("/_deploy/ip")
def client_ip(request: Request):
    return {"ip": request.client.host, "scheme": request.url.scheme,
            "forwarded": request.headers.get("forwarded"), "real_ip": request.headers.get("x-real-ip")}


app.add_api_route("/_deploy/limited", client_ip, methods=["GET"], dependencies=[Depends(enforce_chat_rate_limit)])


@app.get("/_deploy/stream-state")
def current_stream_state():
    return stream_state


@app.post("/_deploy/body")
async def consume_body(request: Request):
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
    return {"bytes": size}


# Replace only the storage-dependent upload endpoint. Keep its actual parser,
# middleware, byte budget and per-file read limit, without Supabase/auth calls.
photo_upload_path = "/campuses/{campus_id}/places/{place_type}/{place_id}/photos"
app.router.routes[:] = [route for route in app.router.routes
                       if getattr(route, "path", None) not in {"/documents/upload", photo_upload_path}]


async def synthetic_upload(file: UploadFile = File(...)):
    try:
        data = read_limited_bytes(file.file, max_size_bytes=get_max_document_size_bytes())
        return {"bytes": len(data)}
    except DocumentTooLargeError:
        raise HTTPException(status_code=413, detail="Upload sintético excedeu o limite.") from None


app.router.routes.append(DocumentUploadRoute("/documents/upload", endpoint=synthetic_upload, methods=["POST"]))


async def synthetic_photo_upload(file: UploadFile = File(...)):
    try:
        data = read_limited_bytes(file.file, max_size_bytes=MAX_PHOTO_BYTES)
        return {"bytes": len(data)}
    except DocumentTooLargeError:
        raise HTTPException(status_code=413, detail="Foto sintética excedeu o limite.") from None


app.router.routes.append(DocumentUploadRoute(photo_upload_path, endpoint=synthetic_photo_upload, methods=["POST"]))
