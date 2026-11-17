"""Adapters that let pubtest's HTTP steps send a suite's service a request.

A suite gives pubtest an `http_client` fixture: a callable taking a method,
a path, headers and a body, and answering an `Answer`. These make one from
the usual kinds of app:

    @pytest.fixture
    def http_client():
        return pubtest.http.asgi(create_app())
"""

from __future__ import annotations

import asyncio
import io
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

__all__ = ["Answer", "asgi", "wsgi"]

Client = Callable[[str, str, Mapping[str, str], bytes | None], "Answer"]


@dataclass
class Answer:
    """What a service answered."""

    status: int
    headers: dict[str, str]
    body: bytes

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

    def json(self) -> Any:
        """The body read as JSON, when a step asks for it."""
        import json  # noqa: PLC0415
        return json.loads(self.body)

    def header(self, name: str) -> str | None:
        """A header, its name compared without case."""

        return next((v for k, v in self.headers.items() if k.lower() == name.lower()), None)


def wsgi(app: Callable[..., Any]) -> Client:
    """A WSGI app (Flask, Django, a plain callable)."""

    def send(method: str, path: str, headers: Mapping[str, str], body: bytes | None) -> Answer:
        url = urlsplit(path)
        environ = {
            "REQUEST_METHOD": method, "PATH_INFO": url.path, "QUERY_STRING": url.query,
            "SERVER_NAME": "localhost", "SERVER_PORT": "80", "SERVER_PROTOCOL": "HTTP/1.1",
            "wsgi.version": (1, 0), "wsgi.url_scheme": "http", "wsgi.input": io.BytesIO(body or b""),
            "wsgi.errors": io.StringIO(), "wsgi.multithread": False, "wsgi.multiprocess": False,
            "wsgi.run_once": True, "CONTENT_LENGTH": str(len(body or b"")),
        }
        for name, value in headers.items():
            key = name.upper().replace("-", "_")
            environ[key if key in ("CONTENT_TYPE", "CONTENT_LENGTH") else f"HTTP_{key}"] = value
        started: dict[str, Any] = {}

        def start_response(status, response_headers, exc_info=None):
            started["status"], started["headers"] = status, response_headers

        chunks = app(environ, start_response)
        try:
            data = b"".join(chunks)
        finally:
            getattr(chunks, "close", lambda: None)()
        return Answer(int(started["status"].split()[0]), dict(started["headers"]), data)

    return send


def asgi(app: Callable[..., Any]) -> Client:
    """An ASGI app (Starlette, FastAPI), called directly, with no server."""

    def send(method: str, path: str, headers: Mapping[str, str], body: bytes | None) -> Answer:
        url = urlsplit(path)
        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
            "scheme": "http", "path": url.path, "raw_path": url.path.encode(), "query_string": url.query.encode(),
            "root_path": "", "server": ("localhost", 80), "client": ("127.0.0.1", 50000),
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        }
        messages = [{"type": "http.request", "body": body or b"", "more_body": False}]
        answer: dict[str, Any] = {"body": b""}

        async def receive():
            return messages.pop(0) if messages else {"type": "http.disconnect"}

        async def respond(message):
            if message["type"] == "http.response.start":
                answer["status"] = message["status"]
                answer["headers"] = {k.decode(): v.decode() for k, v in message.get("headers", [])}
            elif message["type"] == "http.response.body":
                answer["body"] += message.get("body", b"")

        asyncio.run(app(scope, receive, respond))
        return Answer(answer["status"], answer.get("headers", {}), answer["body"])

    return send
