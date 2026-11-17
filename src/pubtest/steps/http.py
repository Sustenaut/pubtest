"""HTTP: a request to the service under test, and its answer."""

from __future__ import annotations

import json
from urllib.parse import urlencode

import pytest
from pytest_bdd import given, parsers, then, when

from ..core import Result, same


@pytest.fixture
def http_client():
    pytest.fail("the HTTP steps need the suite's http_client fixture: pubtest.http.asgi(app), "
                "pubtest.http.wsgi(app), or a callable of its own")


@pytest.fixture
def identity_header() -> str:
    """The header a signed-in person's email comes in, behind the sign-in proxy."""
    return "X-Forwarded-Email"


def _headers(ctx) -> dict:
    if not hasattr(ctx, "headers"):
        ctx.headers = {}
    return ctx.headers


@given(parsers.parse('I am signed in as "{email}"'))
def signed_in(ctx, identity_header, email):
    _headers(ctx)[identity_header] = email


@given("I am not signed in")
def not_signed_in(ctx, identity_header):
    _headers(ctx).pop(identity_header, None)


@given(parsers.parse('requests come from "{origin}"'))
def origin(ctx, origin):
    _headers(ctx)["Origin"] = origin


def send(ctx, http_client, method: str, path: str, body: bytes | None = None, content_type: str | None = None):
    headers = dict(_headers(ctx))
    if content_type:
        headers["Content-Type"] = content_type
    ctx.acting()
    ctx.answer = http_client(method, path, headers, body)
    ctx.ran(Result(value=ctx.answer))
    return ctx.answer


@when(parsers.parse('I GET "{path}"'))
def get(ctx, http_client, path):
    send(ctx, http_client, "GET", path)


@when(parsers.parse('I POST to "{path}" with:'))
def post_json(ctx, http_client, path, docstring):
    send(ctx, http_client, "POST", path, docstring.encode(), "application/json")


@when(parsers.parse('I POST to "{path}" with the form:'))
def post_form(ctx, http_client, path, datatable):
    fields = {row[0]: row[1] for row in datatable[1:]} if datatable and datatable[0][:2] == ["field", "value"] \
        else {row[0]: row[1] for row in datatable}
    send(ctx, http_client, "POST", path, urlencode(fields).encode(), "application/x-www-form-urlencoded")


@when(parsers.parse('I send "{method}" to "{path}"'))
def send_method(ctx, http_client, method, path):
    send(ctx, http_client, method, path)


def _answer(ctx):
    assert getattr(ctx, "answer", None) is not None, "no request was sent"
    return ctx.answer


def _show(answer) -> str:
    return f"{answer.status} {answer.headers}\n{answer.text[:2000]}"


@then(parsers.parse("the answer is {status:d}"))
def answer_is(ctx, status):
    answer = _answer(ctx)
    assert answer.status == status, _show(answer)


@then(parsers.parse('the answer\'s "{name}" is "{wanted}"'))
def answer_header(ctx, name, wanted):
    answer = _answer(ctx)
    assert answer.header(name) == wanted, _show(answer)


@then(parsers.parse('the answer has no "{name}"'))
def answer_no_header(ctx, name):
    answer = _answer(ctx)
    assert answer.header(name) is None, _show(answer)


@then(parsers.parse('the answer includes "{text}" once'))
def answer_includes_once(ctx, text):
    answer = _answer(ctx)
    assert sum(1 for line in answer.text.splitlines() if text in line) == 1, _show(answer)


@then(parsers.parse('the answer includes "{text}"'))
def answer_includes(ctx, text):
    answer = _answer(ctx)
    assert text in answer.text, _show(answer)


@then(parsers.parse('the answer does not include "{text}"'))
def answer_excludes(ctx, text):
    answer = _answer(ctx)
    assert text not in answer.text, _show(answer)


@then("the answer is the JSON:")
def answer_json(ctx, docstring):
    answer = _answer(ctx)
    assert json.loads(answer.body) == json.loads(docstring), _show(answer)


@then(parsers.parse('the answer redirects to "{path}"'))
def answer_redirects(ctx, path):
    answer = _answer(ctx)
    assert 300 <= answer.status < 400 and same(answer.header("Location"), path), _show(answer)
