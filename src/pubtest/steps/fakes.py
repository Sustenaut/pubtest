"""HTTP: fake services the code under test calls, and recorded answers."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pytest_bdd import given, parsers, then


class Fake:
    """One fake service: its answers by "METHOD PATH", and the requests it was sent."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.answers: dict[str, list[tuple[int, str]]] = {}
        self.requests: list[dict] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def _answer(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length).decode("utf-8", "replace") if length else ""
                key = f"{self.command} {self.path}"
                fake.requests.append({"method": self.command, "path": self.path, "body": body,
                                      "headers": dict(self.headers)})
                queue = fake.answers.get(key) or fake.answers.get(f"{self.command} {self.path.split('?')[0]}")
                status, text = (queue.pop(0) if len(queue) > 1 else queue[0]) if queue else (404, "")
                data = text.encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                if text.lstrip().startswith(("{", "[")):
                    self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = _answer

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def answer(self, request: str, status: int, body: str = "") -> None:
        self.answers.setdefault(request, []).append((status, body))

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def _env_name(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name).upper() + "_URL"


def fake(ctx, monkeypatch, name: str) -> Fake:
    if not hasattr(ctx, "fakes"):
        ctx.fakes = {}
    if name not in ctx.fakes:
        ctx.fakes[name] = Fake(name)
        monkeypatch.setenv(_env_name(name), ctx.fakes[name].url)
        ctx.cleanup(ctx.fakes[name].stop)
    return ctx.fakes[name]


@given(parsers.parse('a fake "{name}" service'))
def fake_service(ctx, monkeypatch, name):
    fake(ctx, monkeypatch, name)


@given(parsers.parse('the "{name}" service answers "{request}" with {status:d}'))
def answers(ctx, monkeypatch, name, request, status):
    fake(ctx, monkeypatch, name).answer(request, status)


@given(parsers.parse('the "{name}" service answers "{request}" with {status:d} and:'))
def answers_with(ctx, monkeypatch, name, request, status, docstring):
    fake(ctx, monkeypatch, name).answer(request, status, docstring)


@given(parsers.parse('the answers recorded in "{directory}"'))
def recorded(ctx, monkeypatch, directory):
    """Each JSON file in the directory, in name order, is one answer:
    {"service", "method", "path", "status", "body"}."""
    base = (ctx.directory or Path.cwd()) / directory
    if not base.exists():
        base = Path(directory)
    ctx.recorded = []
    for path in sorted(base.glob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        body = entry.get("body", "")
        body = body if isinstance(body, str) else json.dumps(body)
        fake(ctx, monkeypatch, entry["service"]).answer(f"{entry['method']} {entry['path']}", entry["status"], body)
        ctx.recorded.append(entry)


def _asked(ctx, name: str) -> list[dict]:
    fakes = getattr(ctx, "fakes", {})
    assert name in fakes, f"there is no fake {name} service"
    return fakes[name].requests


@then(parsers.parse('the "{name}" service was asked "{request}"'))
def was_asked(ctx, name, request):
    asked = [f"{r['method']} {r['path']}" for r in _asked(ctx, name)]
    assert request in asked or request in [a.split("?")[0] for a in asked], f"{name} was asked {asked}"


@then(parsers.parse('the "{name}" service was sent:'))
def was_sent(ctx, name, docstring):
    want = json.loads(docstring)
    bodies = []
    for request in _asked(ctx, name):
        try:
            bodies.append(json.loads(request["body"]))
        except ValueError:
            bodies.append(request["body"])
    assert want in bodies, f"{name} was sent {bodies}"


@then(parsers.parse('the "{name}" service was asked nothing'))
def asked_nothing(ctx, name):
    assert not _asked(ctx, name), f"{name} was asked {_asked(ctx, name)}"


@then("nothing was sent")
def nothing_sent(ctx):
    sent = {name: f.requests for name, f in getattr(ctx, "fakes", {}).items() if f.requests}
    assert not sent, f"sent: {sent}"


@then("every recorded answer was used")
def recorded_used(ctx):
    used = {f"{r['method']} {r['path']}" for f in getattr(ctx, "fakes", {}).values() for r in f.requests}
    unused = [f"{e['method']} {e['path']}" for e in getattr(ctx, "recorded", [])
              if f"{e['method']} {e['path']}" not in used]
    assert not unused, f"not used: {unused}"
