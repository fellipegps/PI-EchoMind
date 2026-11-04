"""Cancel chat generation while awaiting the next token after disconnection.

ASGI 2.4 permits detecting disconnection on send(), but that alone cannot stop
a model request that is waiting between tokens. Keep an active receive listener
for this response only, preserving the server's actual ASGI scope/version.
"""
from __future__ import annotations

import anyio
from starlette.responses import StreamingResponse
from starlette.types import Receive, Scope, Send


class ChatStreamingResponse(StreamingResponse):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await super().__call__(scope, receive, send)
            return

        async with anyio.create_task_group() as group:
            async def stream() -> None:
                try:
                    await self.stream_response(send)
                except OSError:
                    # ASGI 2.4 also reports a closed peer through send().
                    pass
                finally:
                    close = getattr(self.body_iterator, "aclose", None)
                    if close is not None:
                        # Also finalize a generator suspended at yield if send
                        # fails, without allowing its cleanup to wait forever.
                        with anyio.move_on_after(1, shield=True):
                            await close()
                    group.cancel_scope.cancel()

            group.start_soon(stream)
            await self.listen_for_disconnect(receive)
            group.cancel_scope.cancel()

        if self.background is not None:
            await self.background()
