"""Adapters that let pubtest's HTTP steps send a suite's service a request.

A suite gives pubtest an `http_client` fixture: a callable taking a method,
a path, headers and a body, and answering an `Answer`. These make one from
the usual kinds of app:

    @pytest.fixture
    def http_client():
        return pubtest.http.asgi(create_app())

or `pubtest.http.wsgi(app)`, or `pubtest.http.url(base)` for a server
already listening.
"""

from __future__ import annotations

import asyncio
import io
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlsplit

__all__ = ["Answer", "asgi", "url", "wsgi"]

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
    """An ASGI app (Starlette, FastAPI), called directly, with no server.

    As a server does, it gives the app the path percent-decoded (`raw_path`
    the bytes as sent), a Content-Length for a body, and the body; then it
    keeps the connection until the answer is complete, so an app listening
    for the client to leave (a streamed answer) is not cut short. The client
    leaves only once the answer is complete: an app that waits for
    `http.disconnect` before it answers at all waits forever here."""

    def send(method: str, path: str, headers: Mapping[str, str], body: bytes | None) -> Answer:
        url = urlsplit(path)
        sent = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
        if body is not None and not any(k == b"content-length" for k, _ in sent):
            sent.append((b"content-length", str(len(body)).encode()))
        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
            "scheme": "http", "path": unquote(url.path), "raw_path": url.path.encode(),
            "query_string": url.query.encode(), "root_path": "", "server": ("localhost", 80),
            "client": ("127.0.0.1", 50000), "headers": sent,
        }
        answer: dict[str, Any] = {"body": b""}

        async def run() -> None:
            messages = [{"type": "http.request", "body": body or b"", "more_body": False}]
            complete = asyncio.Event()

            async def receive():
                if messages:
                    return messages.pop(0)
                await complete.wait()
                return {"type": "http.disconnect"}

            async def respond(message):
                if message["type"] == "http.response.start":
                    answer["status"] = message["status"]
                    answer["headers"] = {k.decode(): v.decode()
                                         for k, v in message.get("headers", [])}
                elif message["type"] == "http.response.body":
                    answer["body"] += message.get("body", b"")
                    if not message.get("more_body", False):
                        complete.set()

            try:
                await app(scope, receive, respond)
            finally:
                complete.set()

        asyncio.run(run())
        return Answer(answer["status"], answer.get("headers", {}), answer["body"])

    return send


def url(base: str) -> Client:
    """A server already listening at `base` (`http://127.0.0.1:8000`), its
    path prefix kept. It does not follow redirects."""
    import http.client  # noqa: PLC0415

    root = urlsplit(base)
    if root.scheme not in ("http", "https") or not root.netloc:
        raise ValueError(f"{base!r} is not an http or https address")
    connection = http.client.HTTPSConnection if root.scheme == "https" else http.client.HTTPConnection

    def send(method: str, path: str, headers: Mapping[str, str], body: bytes | None) -> Answer:
        target = root.path.rstrip("/") + (path if path.startswith("/") else "/" + path)
        conn = connection(root.netloc, timeout=120)
        try:
            conn.request(method, target, body=body, headers=dict(headers))
            response = conn.getresponse()
            return Answer(response.status, dict(response.getheaders()), response.read())
        finally:
            conn.close()

    return send
