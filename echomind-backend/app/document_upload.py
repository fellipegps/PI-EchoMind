"""Barreira de bytes anterior ao parser, exclusiva do upload documental."""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import HTTPException, Request, Response
from fastapi.routing import APIRoute
from multipart.multipart import parse_options_header
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .document_ingestion import InvalidDocumentConfigurationError, get_max_document_size_bytes


# Orcamento fixo para boundaries, cabecalhos das partes e metadados opcionais.
# Nao aumenta o limite do arquivo, validado separadamente pelo endpoint.
MULTIPART_ENVELOPE_BYTES = 64 * 1024
_BODY_EXCEEDED = "echomind.document_upload.body_exceeded"
_CONFIG_INVALID = "echomind.document_upload.config_invalid"


class DocumentUploadLimitMiddleware:
    """Conta receive antes dos middlewares que escutam desconexao da resposta."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "").removeprefix(scope.get("root_path", ""))
        if scope["type"] != "http" or scope["method"] != "POST" or path != "/documents/upload":
            await self.app(scope, receive, send)
            return
        try:
            body_limit = get_max_document_size_bytes() + MULTIPART_ENVELOPE_BYTES
        except InvalidDocumentConfigurationError:
            scope[_CONFIG_INVALID] = True
            body_limit = 0

        received_bytes = 0
        stopped = bool(scope.get(_CONFIG_INVALID))
        response_complete = asyncio.Event()

        async def receive_limited() -> Message:
            nonlocal received_bytes, stopped
            if stopped:
                # BaseHTTPMiddleware escuta desconexao enquanto envia a resposta.
                # Nao deixe esse listener drenar o restante de um upload rejeitado.
                await response_complete.wait()
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > body_limit:
                    stopped = True
                    # O chunk excedente nao chega ao parser, independentemente
                    # de ausencia, subestimativa ou erro no Content-Length.
                    scope[_BODY_EXCEEDED] = True
                    # Sinalize EOF aos middlewares; a rota transforma o marcador
                    # em 413 dentro do ExceptionMiddleware, preservando CORS.
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        async def send_response(message: Message) -> None:
            nonlocal stopped
            if message["type"] == "http.response.start":
                stopped = True
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                response_complete.set()

        await self.app(scope, receive_limited, send_response)


class DocumentUploadRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def bounded_upload(original_request: Request) -> Response:
            if original_request.scope.get(_CONFIG_INVALID):
                raise HTTPException(status_code=500, detail="Configuração inválida do limite de upload.")

            async def receive_checked() -> Message:
                message = await original_request.receive()
                if original_request.scope.get(_BODY_EXCEEDED):
                    raise HTTPException(status_code=413, detail="O arquivo excede o tamanho maximo permitido.")
                return message

            request = Request(original_request.scope, receive=receive_checked)
            parser = None
            try:
                content_type, _params = parse_options_header(request.headers.get("content-type"))
                if content_type == b"multipart/form-data":
                    parser = MultiPartParser(request.headers, request.stream(), max_files=1)
                    try:
                        # FastAPI 0.111 chama request.form() antes das dependencias.
                        # Compartilhar o cache evita uma segunda leitura do stream.
                        request._form = await parser.parse()
                    except MultiPartException as exc:
                        detail = (
                            "Envie exatamente um arquivo por requisição."
                            if parser._current_files > 1 else exc.message
                        )
                        raise HTTPException(status_code=400, detail=detail) from exc
                    except HTTPException:
                        raise
                    except Exception as exc:
                        # Mantem o contrato de erro de parsing do FastAPI.
                        raise HTTPException(status_code=400, detail="There was an error parsing the body") from exc
                return await handler(request)
            finally:
                if parser is not None:
                    # Starlette 0.37.2 so fecha estes temporarios em MultiPartException.
                    # Inclui HTTP 413, desconexao, erro do parser e cancelamento.
                    for temporary_file in parser._files_to_close_on_error:
                        temporary_file.close()

        return bounded_upload
