"""pubtest's own suite: the steps a suite would write itself, to drive the
library's steps, the same text as test/steps/ has in Node."""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs

import pytest
from pytest_bdd import parsers, then, when

import pubtest.http

os.environ.setdefault("GREET_BIN_DIR", str(Path(__file__).parent / "bin"))


@when(parsers.parse("I add {a:d} and {b:d}"))
def add(ctx, a, b):
    ctx.attempt(lambda: a + b)


@when(parsers.parse("I check that {a:d} is more than {b:d}"))
def more(ctx, a, b):
    ctx.attempt(lambda: a > b)


@when(parsers.parse('I give back the text "{text}"'))
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


def main(argv):
    """A command-line main, called in-process, as pubrules-style suites call theirs."""
    import sys  # noqa: PLC0415
    if argv and argv[0].startswith("--"):
        print("usage: main [NAME]", file=sys.stderr)
        print(f"no such option: {argv[0]}", file=sys.stderr)
        raise SystemExit(2)
    print("ok")


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
