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
        self.answers: dict[str, list[tuple[int, str, dict]]] = {}
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
                status, text, headers = (queue.pop(0) if len(queue) > 1 else queue[0]) if queue else (404, "", {})
                data = text.encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                if text.lstrip().startswith(("{", "[")) and "content-type" not in {k.lower() for k in headers}:
                    self.send_header("Content-Type", "application/json")
                for name, value in headers.items():
                    self.send_header(name, value)
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

    def answer(self, request: str, status: int, body: str = "", headers: dict | None = None) -> None:
        self.answers.setdefault(request, []).append((status, body, headers or {}))

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def _env_name(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name).upper() + "_URL"


def fake(pubtest_ctx, monkeypatch, name: str) -> Fake:
    if not hasattr(pubtest_ctx, "fakes"):
        pubtest_ctx.fakes = {}
    if name not in pubtest_ctx.fakes:
        pubtest_ctx.fakes[name] = Fake(name)
        monkeypatch.setenv(_env_name(name), pubtest_ctx.fakes[name].url)
        pubtest_ctx.cleanup(pubtest_ctx.fakes[name].stop)
    return pubtest_ctx.fakes[name]


@given(parsers.parse('a fake "{name}" service'))
def fake_service(pubtest_ctx, monkeypatch, name):
    fake(pubtest_ctx, monkeypatch, name)


@given(parsers.parse('the "{name}" service answers "{request}" with {status:d}'))
def answers(pubtest_ctx, monkeypatch, name, request, status):
    fake(pubtest_ctx, monkeypatch, name).answer(request, status)


@given(parsers.parse('the "{name}" service answers "{request}" with {status:d} and:'))
def answers_with(pubtest_ctx, monkeypatch, name, request, status, docstring):
    fake(pubtest_ctx, monkeypatch, name).answer(request, status, docstring)


@given(parsers.parse('the "{name}" service answers "{request}" with {status:d} and the header "{header}" set to "{value}"'))
def answers_with_header(pubtest_ctx, monkeypatch, name, request, status, header, value):
    fake(pubtest_ctx, monkeypatch, name).answer(request, status, "", {header: value})


@given(parsers.parse('the answers recorded in "{directory}"'))
def recorded(pubtest_ctx, monkeypatch, directory):
    """Each JSON file in the directory, in name order, is one answer:
    {"service", "method", "path", "status", "body"}."""
    base = (pubtest_ctx.directory or Path.cwd()) / directory
    if not base.exists():
        base = Path(directory)
    pubtest_ctx.recorded = []
    for path in sorted(base.glob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        body = entry.get("body", "")
        body = body if isinstance(body, str) else json.dumps(body)
        fake(pubtest_ctx, monkeypatch, entry["service"]).answer(f"{entry['method']} {entry['path']}", entry["status"], body)
        pubtest_ctx.recorded.append(entry)


def _asked(pubtest_ctx, name: str) -> list[dict]:
    fakes = getattr(pubtest_ctx, "fakes", {})
    assert name in fakes, f"there is no fake {name} service"
    return fakes[name].requests


@then(parsers.re(r'the "(?P<name>[^"]+)" service was asked "(?P<request>[^"]+)"'))
def was_asked(pubtest_ctx, name, request):
    asked = [f"{r['method']} {r['path']}" for r in _asked(pubtest_ctx, name)]
    assert request in asked or request in [a.split("?")[0] for a in asked], f"{name} was asked {asked}"


def _requests(pubtest_ctx, name: str, request: str) -> list[dict]:
    """The requests `name` was asked that are `request`, "METHOD PATH", its
    query left out unless `request` names one."""
    return [r for r in _asked(pubtest_ctx, name)
            if request in (f"{r['method']} {r['path']}", f"{r['method']} {r['path'].split('?')[0]}")]


@then(parsers.parse('the "{name}" service was asked "{request}" {count:d} times'))
def asked_times(pubtest_ctx, name, request, count):
    found = _requests(pubtest_ctx, name, request)
    assert len(found) == count, f"{name} was asked {request} {len(found)} times"


@then(parsers.parse('the "{name}" service was asked "{request}" with the header "{header}" set to "{value}"'))
def asked_with_header(pubtest_ctx, name, request, header, value):
    found = _requests(pubtest_ctx, name, request)
    seen = [{k.lower(): v for k, v in r["headers"].items()}.get(header.lower()) for r in found]
    assert value in seen, f"{name} was asked {request} with {header} {seen}"


@then(parsers.parse('the "{name}" service was sent:'))
def was_sent(pubtest_ctx, name, docstring):
    want = json.loads(docstring)
    bodies = []
    for request in _asked(pubtest_ctx, name):
        try:
            bodies.append(json.loads(request["body"]))
        except ValueError:
            bodies.append(request["body"])
    assert want in bodies, f"{name} was sent {bodies}"


@then(parsers.parse('the "{name}" service was asked nothing'))
def asked_nothing(pubtest_ctx, name):
    assert not _asked(pubtest_ctx, name), f"{name} was asked {_asked(pubtest_ctx, name)}"


@then("nothing was sent")
def nothing_sent(pubtest_ctx):
    sent = {name: f.requests for name, f in getattr(pubtest_ctx, "fakes", {}).items() if f.requests}
    assert not sent, f"sent: {sent}"


@then("every recorded answer was used")
def recorded_used(pubtest_ctx):
    used = {f"{r['method']} {r['path']}" for f in getattr(pubtest_ctx, "fakes", {}).values() for r in f.requests}
    unused = [f"{e['method']} {e['path']}" for e in getattr(pubtest_ctx, "recorded", [])
              if f"{e['method']} {e['path']}" not in used]
    assert not unused, f"not used: {unused}"
