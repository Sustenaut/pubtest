"""Steps for python-features/adapters.feature (the ASGI adapter) and
python-only.feature (what only Python has)."""

import asyncio
import json
import os
import subprocess

from pytest_bdd import given, scenarios, when

from pubtest.steps import phrase

import pubtest.http

scenarios("../tests/python-features/adapters.feature", "../tests/python-features/python-only.feature")


async def stream(receive, send):
    """A streamed answer that, as Starlette's does, listens meanwhile for the
    client leaving, and stops when it does."""

    async def parts():
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
        for part in (b"one ", b"two ", b"three"):
            await send({"type": "http.response.body", "body": part, "more_body": True})
            await asyncio.sleep(0.01)
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    async def left():
        while (await receive())["type"] != "http.disconnect":
            pass

    tasks = {asyncio.ensure_future(parts()), asyncio.ensure_future(left())}
    _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()


async def app(scope, receive, send):
    """The service under test in http.feature, as an ASGI app."""
    message = await receive()
    body = message.get("body", b"")
    headers = dict(scope["headers"])
    who = headers.get(b"x-forwarded-email", b"").decode()
    path, method = scope["path"], scope["method"]
    if path == "/stream":
        await stream(receive, send)
        return
    if path.startswith("/files/"):
        status, kind, text, extra = 200, b"text/plain", f"path {path} raw {scope['raw_path'].decode()}", []
    elif path == "/upload":
        length = headers.get(b"content-length", b"-").decode()
        status, kind, text, extra = 200, b"text/plain", f"{method} {len(body)} bytes, length {length}", []
    elif path == "/hello":
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


@given(phrase('the service under test is the "{name}" service, listening'), target_fixture="http_client")
def listening(name):
    return pubtest.http.url(os.environ[name.upper() + "_URL"])


@when(phrase('the suite\'s own step runs "{command}" and keeps what it did'), target_fixture="result")
def own_result(command):
    """A suite's When that sets the result fixture to a run of its own."""
    return subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
