"""HTTP middlewares shared by the FastAPI app."""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import reset_request_id, set_request_id

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Tag every request with a stable id and echo it back in the response.

    The id is honoured if the client already supplies one (so a frontend
    or upstream load balancer can correlate its own logs); otherwise we
    generate a fresh UUID4. The value is stored in a contextvar via
    `set_request_id`, so log records emitted during the request — even
    from sub-tasks — carry the same id thanks to the
    `_RequestIDFilter` configured in `app.core.logging`.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming or uuid.uuid4().hex
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            reset_request_id(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
