"""pubtest's own suite: the steps a suite would write itself, to drive the
library's steps, the same text as test/steps/ has in Node."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs

import pytest
from pytest_bdd import given, parsers, then, when

import pubtest.http
from pubtest import cassettes
from pubtest.steps import phrase

os.environ.setdefault("GREET_BIN_DIR", str(Path(__file__).parent / "bin"))


@when(parsers.parse("I add {a:d} and {b:d}"))
def add(ctx, a, b):
    ctx.attempt(lambda: a + b)


@when(parsers.parse("I check that {a:d} is more than {b:d}"))
def more(ctx, a, b):
    ctx.attempt(lambda: a > b)


@when(phrase('I give back the text "{text}"'))
def give_back(ctx, text):
    ctx.attempt(lambda: text)


@then("the result is not the number 2")
def not_number(ctx):
    assert ctx.result == "2" and ctx.result != 2


@when(parsers.parse('I list the words of "{text}"'))
def words(ctx, text):
    ctx.attempt(lambda: text.split())


@when("I list the people")
def people(ctx):
    ctx.attempt(lambda: [{"name": "Ann", "age": 30}, {"name": "Ben", "age": 41}])


@when("I find nothing")
def nothing(ctx):
    ctx.attempt(lambda: None)


@when(parsers.parse("I divide {a:d} by {b:d}"))
def divide(ctx, a, b):
    ctx.attempt(lambda: a / b)


class Problem(Exception):
    """The base of the suite's own refusals."""


class NotFound(Problem):
    def __init__(self, key):
        super().__init__(f"no {key}")
        self.key = key
        self.detail = {"code": 404}


@when(phrase('I look up "{key}"'))
def look_up(ctx, key):
    def lookup():
        raise NotFound(key)
    ctx.attempt(lookup)


@when("I describe the release")
def describe_release(ctx):
    ctx.attempt(lambda: {"version": "v1.2.3", "tags": ["stable", "lts"], "note": ""})


def main(argv):
    """A command-line main, called in-process, as pubrules-style suites call theirs."""
    import sys  # noqa: PLC0415
    if argv and argv[0].startswith("--"):
        print("usage: main [NAME]", file=sys.stderr)
        print(f"no such option: {argv[0]}", file=sys.stderr)
        raise SystemExit(2)
    print("ok")


@when(parsers.parse('I copy "{source}" from the repository'))
def copy_from_repository(ctx, pubtest_repository, source):
    from pubtest.steps.files import copied  # noqa: PLC0415
    ctx.attempt(lambda: copied(ctx, pubtest_repository, "copy", source))


@when(parsers.parse('I run main with "{args}"'))
def run_main(ctx, args):
    ctx.attempt(lambda: main(args.split()))


@then(parsers.parse('the secret is found in "{where}"'))
def secret_found(ctx, where):
    from pubtest.steps.secrets import produced  # noqa: PLC0415
    assert any(s in produced(ctx).get(where, "") for s in ctx.secrets), produced(ctx)


def app(environ, start_response):
    """The service under test in http.feature."""
    path, method = environ["PATH_INFO"], environ["REQUEST_METHOD"]
    who = environ.get("HTTP_X_FORWARDED_EMAIL")
    body = environ["wsgi.input"].read(int(environ.get("CONTENT_LENGTH") or 0))

    def answer(status, text, kind="text/plain", extra=()):
        start_response(status, [("Content-Type", kind), *extra])
        return [text.encode()]

    if path == "/hello":
        return answer("200 OK", f"hello, {who}") if who else answer("403 Forbidden", "sign in")
    if path == "/echo" and method in ("POST", "PUT"):
        return answer("200 OK", json.dumps({"echo": json.loads(body)}), "application/json")
    if path == "/form" and method == "POST":
        fields = parse_qs(body.decode())
        return answer("200 OK", "&".join(f"{k}={v[0]}" for k, v in fields.items()))
    if path == "/old":
        return answer("302 Found", "", extra=[("Location", "/new")])
    if path == "/forecast":
        asked = urllib.request.Request(os.environ["WEATHER_URL"] + "/today", headers={"X-Client": "pubtest-app"})
        with urllib.request.urlopen(asked) as r:
            sky = [("X-Sky", r.headers["X-Sky"])] if r.headers.get("X-Sky") else []
            return answer("200 OK", r.read().decode(), extra=sky)
    if path == "/upload":
        kind = environ.get("CONTENT_TYPE", "-")
        return answer("200 OK", f"{method} {kind} {len(body)} {environ.get('HTTP_X_TOKEN', '-')}")
    return answer("404 Not Found", "")


@pytest.fixture
def http_client():
    return pubtest.http.wsgi(app)


INNER_FEATURE = """Feature: Inner
  Scenario: Inner
    When I divide 1 by 0
    {then}
"""
INNER_STEPS = '''from pytest_bdd import parsers, scenarios, then, when
scenarios("inner.feature")


@when(parsers.parse("I divide {a:d} by {b:d}"))
def divide(ctx, a, b):
    ctx.attempt(lambda: a / b)


@then("nothing else is checked")
def nothing_else():
    pass
'''


@when(parsers.parse("a scenario whose action is refused, and that reads {what}, runs"), target_fixture="inner")
def inner_run(pytester, what):
    then_line = "Then nothing else is checked" if what == "no refusal" else "Then it is refused"
    pytester.makefile(".feature", inner=INNER_FEATURE.format(then=then_line))
    pytester.makepyfile(test_inner=INNER_STEPS)
    pytester.makeini("[pytest]\nbdd_features_base_dir = .\naddopts = -p no:pubrules\n")
    return pytester.runpytest()


@then(parsers.parse('that scenario fails, saying "{text}"'))
def inner_fails(inner, text):
    assert inner.ret != 0 and text in inner.stdout.str(), inner.stdout.str()


@then("that scenario passes")
def inner_passes(inner):
    assert inner.ret == 0, inner.stdout.str()


PROPERTY_SUITE = '''from pathlib import Path
from hypothesis import given, strategies as st

@given(st.integers())
def test_property(x):
    with Path("examples").open("a") as f:
        f.write("x\\n")
'''


@when(parsers.parse('a suite with one property runs with PUBRULES_FUZZ_RUNS at "{runs}"'),
      target_fixture="inner")
def property_suite(pytester, monkeypatch, runs):
    monkeypatch.setenv("PUBRULES_FUZZ_RUNS", runs)
    pytester.makepyfile(test_property=PROPERTY_SUITE)
    pytester.makeini("[pytest]\naddopts = -p no:pubrules\n")
    return pytester.runpytest()


@then(parsers.parse("that property ran {count:d} examples"))
def property_ran(inner, pytester, count):
    assert inner.ret == 0, inner.stdout.str()
    assert len((pytester.path / "examples").read_text().splitlines()) == count


@then(parsers.parse('that suite is refused, saying "{text}"'))
def suite_refused(inner, text):
    said = inner.stdout.str() + inner.stderr.str()
    assert inner.ret == pytest.ExitCode.USAGE_ERROR and text in said, said


# --- calls to outside services (integrations.feature, recording.feature) ---------

os.environ.setdefault("PUBTEST_BIN_DIR", str(Path(sys.executable).parent))


class ExampleNetwork:
    """What record mode records through in pubtest's own suite: GitHub's shape of
    answer, {"name": the URL's last part, "updated_at": now}, never the network."""

    def send(self, request, timeout):
        from integrations.calls import Response  # noqa: PLC0415
        body = {"name": request.url.rstrip("/").rsplit("/", 1)[-1],
                "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        return Response(200, json.dumps(body).encode(), headers={"Content-Type": "application/json"})


cassettes.network = ExampleNetwork


def example_get(url):
    from integrations.calls import Caller, Request  # noqa: PLC0415
    return Caller("pubtest", "suite").call("github.repo-ops", "call", Request("GET", url)).json()


@when(phrase('the example client gets "{url}"'))
def example_client_gets(ctx, url):
    ctx.attempt(lambda: example_get(url))


@when(phrase('the example client gets the repository "{logical}"'))
def example_client_gets_repository(ctx, logical):
    real = ctx.tape.names_of("pubtest.example")[logical]
    ctx.attempt(lambda: example_get(f"https://api.github.com/repos/pubtest-example/{real}"))


INNER_SUITE = '''import json
import os
from datetime import datetime, timezone
from pathlib import Path

from integrations.calls import Caller, Request, Response
from pytest_bdd import scenarios, when

from pubtest import cassettes
from pubtest.steps import phrase

scenarios(".")
os.environ["PATH"] = str(Path(__file__).parent.parent / "bin") + os.pathsep + os.environ["PATH"]


class Network:
    def send(self, request, timeout):
        body = {"name": request.url.rstrip("/").rsplit("/", 1)[-1],
                "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        return Response(200, json.dumps(body).encode(), headers={"Content-Type": "application/json"})


cassettes.network = Network


@when(phrase('the inner client gets "{url}"'))
def gets(ctx, url):
    ctx.attempt(lambda: Caller("inner", "suite").call("github.repo-ops", "call", Request("GET", url)).json())
'''

INNER_CLIENT = '''#!{python}
import json
import sys

from integrations.calls import Caller, Request

print(json.dumps(Caller("inner", "program").call("github.repo-ops", "call", Request("GET", sys.argv[1])).json()))
'''

# What a harness sets for the programs it runs, which an inner suite must not inherit.
HARNESS = ("PUBTEST_RUN", "INTEGRATIONS_MODE", "INTEGRATIONS_CASSETTE", "INTEGRATIONS_CASSETTES",
           "INTEGRATIONS_CASSETTE_REPORT", "PUBTEST_ONLY", "PUBTEST_PLAN", "PUBTEST_RECORD", "PUBTEST_CASSETTES")


@given(phrase('an inner suite with the feature "{name}":'))
def inner_suite(ctx, name, docstring):
    root = ctx.directory
    (root / "features").mkdir(exist_ok=True)
    (root / "features" / name).write_text(docstring + "\n", encoding="utf-8")
    (root / "tests").mkdir(exist_ok=True)
    (root / "tests" / "pytest.ini").write_text(
        "[pytest]\nbdd_features_base_dir = ../features/\naddopts = -p no:pubrules -p no:cacheprovider\n", encoding="utf-8")
    (root / "tests" / "test_inner.py").write_text(INNER_SUITE, encoding="utf-8")
    (root / "bin").mkdir(exist_ok=True)
    client = root / "bin" / "inner-client"
    client.write_text(INNER_CLIENT.replace("{python}", sys.executable), encoding="utf-8")
    client.chmod(0o755)


@when("the inner suite runs")
def inner_suite_runs(ctx):
    import subprocess  # noqa: PLC0415
    from pubtest.core import Result  # noqa: PLC0415
    env = {k: v for k, v in os.environ.items() if k not in HARNESS}
    ctx.acting()
    argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    done = subprocess.run(argv, cwd=ctx.directory / "tests", env=env, capture_output=True, text=True, check=False,
                          timeout=300)
    ctx.ran(Result(code=done.returncode, stdout=done.stdout, stderr=done.stderr, argv=argv))


@then(phrase('the inner run says "{text}"'))
def inner_run_says(ctx, text):
    said = ctx.outcome.stdout + ctx.outcome.stderr
    assert text in said, said
