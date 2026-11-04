"""Ограничивает тело загрузки до создания большого multipart spool-файла."""

from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class UploadLimitMiddleware:
    """Проверяет размер тела, включая запросы без Content-Length."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Не допускает неограниченное заполнение временного каталога загрузкой."""
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != "/documents":
            await self.app(scope, receive, send)
            return
        received = 0
        response = JSONResponse(
            status_code=413,
            content={"error": {
                "code": "upload_too_large", "message": "Превышен размер загрузки.",
            }},
        )

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > self.max_bytes:
                raise MultiPartException("Превышен размер загрузки.")
            return message

        async def limited_send(message: Message) -> None:
            if received <= self.max_bytes:
                await send(message)
            elif message["type"] == "http.response.start":
                await response(scope, receive, send)

        try:
            await self.app(scope, limited_receive, limited_send)
        except MultiPartException:
            if received <= self.max_bytes:
                raise
            await response(scope, receive, send)
