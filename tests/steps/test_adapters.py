"""Steps for python-features/adapters.feature: the ASGI adapter."""

import json

import pytest
from pytest_bdd import given, scenarios

import pubtest.http

scenarios("../tests/python-features/adapters.feature")


async def app(scope, receive, send):
    """The service under test in http.feature, as an ASGI app."""
    message = await receive()
    body = message.get("body", b"")
    headers = dict(scope["headers"])
    who = headers.get(b"x-forwarded-email", b"").decode()
    path, method = scope["path"], scope["method"]
    if path == "/hello":
        status, kind, text = (200, b"text/plain", f"hello, {who}") if who else (403, b"text/plain", "sign in")
        extra = []
    elif path == "/echo" and method == "POST":
        status, kind, text, extra = 200, b"application/json", json.dumps({"echo": json.loads(body)}), []
    elif path == "/old":
        status, kind, text, extra = 302, b"text/plain", "", [(b"location", b"/new")]
    else:
        status, kind, text, extra = 404, b"text/plain", "", []
    await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", kind), *extra]})
    await send({"type": "http.response.body", "body": text.encode()})


@given("the service under test is its ASGI version", target_fixture="http_client")
def asgi_version():
    return pubtest.http.asgi(app)
