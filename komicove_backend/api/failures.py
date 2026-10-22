"""Safe request diagnostics and transient dependency failure classification."""

from __future__ import annotations

import logging
import re
import traceback
import uuid

import requests
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, DisconnectionError, OperationalError, TimeoutError as PoolTimeoutError
from starlette.datastructures import Headers

from komicove_backend.catalog.assets import RemoteStorageError
from komicove_backend.catalog.b2_storage import StorageConfigurationError


log = logging.getLogger("uvicorn.error")
_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}\Z")
_UNAVAILABLE_STATES = {"53300", "53400", "57P01", "57P02", "57P03"}


def _causes(error: BaseException):
    current: BaseException | None = error
    for _ in range(6):
        if current is None:
            break
        yield current
        current = current.__cause__ or current.__context__


def _status(error: Exception) -> int:
    if isinstance(error, StorageConfigurationError):
        return 500
    if isinstance(error, requests.Timeout):
        return 504
    if isinstance(error, requests.RequestException):
        return 503
    if isinstance(error, PoolTimeoutError):
        return 504
    if isinstance(error, DisconnectionError):
        return 503
    if isinstance(error, DBAPIError):
        state = getattr(error.orig, "sqlstate", None) or getattr(error.orig, "pgcode", None)
        if state == "57014":
            return 504
        if error.connection_invalidated or (isinstance(state, str) and
                                           (state.startswith("08") or state in _UNAVAILABLE_STATES)):
            return 503
        if isinstance(error, OperationalError) and type(error.orig).__module__.startswith("psycopg") and state is None:
            return 503
        return 500
    if isinstance(error, RemoteStorageError):
        if any(isinstance(cause, (requests.Timeout, TimeoutError)) or
               type(cause).__name__ in {"ReadTimeoutError", "ConnectTimeoutError"}
               for cause in _causes(error)):
            return 504
        return 503
    return 500


_DETAILS = {
    500: "Erro interno do servidor. / Internal server error.",
    503: "Serviço temporariamente indisponível. / Service temporarily unavailable.",
    504: "Tempo limite do serviço excedido. / Service timed out.",
}


class RequestDiagnostics:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        supplied = Headers(scope=scope).get("x-request-id", "")
        request_id = supplied if _REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex
        status = 500
        started = False

        async def send_with_id(message):
            nonlocal status, started
            if message["type"] == "http.response.start":
                status = message["status"]
                started = True
                message["headers"].append((b"x-request-id", request_id.encode("ascii")))
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception as error:
            status = _status(error)
            # SQL and storage exception messages can contain URLs, tokens or query values.
            frames = traceback.extract_tb(error.__traceback__)
            location = ",".join(f"{frame.name}:{frame.lineno}" for frame in frames[-5:])
            route = getattr(scope.get("route"), "path", "unknown")
            log.error("request_id=%s method=%s route=%s status=%s error=%s location=%s",
                      request_id, scope["method"], route, status, type(error).__name__, location)
            if started:
                raise
            await JSONResponse(status_code=status, content={"detail": _DETAILS[status]})(
                scope, receive, send_with_id
            )
        finally:
            route = getattr(scope.get("route"), "path", "unknown")
            log.info("request_id=%s method=%s route=%s status=%s",
                     request_id, scope["method"], route, status)
