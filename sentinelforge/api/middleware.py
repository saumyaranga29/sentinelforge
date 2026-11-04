import time
import uuid
from starlette.types import ASGIApp, Receive, Scope, Send

from sentinelforge.utils.logging import get_logger, request_id_ctx

logger = get_logger("sentinelforge.api.middleware")


class RequestContextMiddleware:
    """Pure ASGI middleware attaching a unique request ID and structured logging to every request."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract or generate unique Request ID
        headers = dict(scope.get("headers", []))
        req_id = headers.get(b"x-request-id", b"").decode("latin1") or f"req_{uuid.uuid4().hex[:12]}"
        token = request_id_ctx.set(req_id)
        start_time = time.perf_counter()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers.append((b"x-request-id", req_id.encode("latin1")))
                message["headers"] = response_headers
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                logger.info(
                    f"{scope.get('method')} {scope.get('path')} status={message.get('status')} duration={duration_ms}ms"
                )
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            request_id_ctx.reset(token)
