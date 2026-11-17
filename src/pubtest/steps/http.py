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


def _headers(pubtest_ctx) -> dict:
    if not hasattr(pubtest_ctx, "headers"):
        pubtest_ctx.headers = {}
    return pubtest_ctx.headers


@given(parsers.parse('I am signed in as "{email}"'))
def signed_in(pubtest_ctx, identity_header, email):
    _headers(pubtest_ctx)[identity_header] = email


@given("I am not signed in")
def not_signed_in(pubtest_ctx, identity_header):
    _headers(pubtest_ctx).pop(identity_header, None)


@given(parsers.parse('requests carry the header "{name}" set to "{value}"'))
def carry_header(pubtest_ctx, name, value):
    _headers(pubtest_ctx)[name] = value


@given(parsers.parse('requests come from "{origin}"'))
def origin(pubtest_ctx, origin):
    _headers(pubtest_ctx)["Origin"] = origin


def send(pubtest_ctx, http_client, method: str, path: str, body: bytes | None = None, content_type: str | None = None):
    headers = dict(_headers(pubtest_ctx))
    if content_type:
        headers["Content-Type"] = content_type
    pubtest_ctx.acting()
    pubtest_ctx.answer = http_client(method, path, headers, body)
    pubtest_ctx.ran(Result(value=pubtest_ctx.answer))
    return pubtest_ctx.answer


@when(parsers.parse('I GET "{path}"'))
def get(pubtest_ctx, http_client, path):
    send(pubtest_ctx, http_client, "GET", path)


@when(parsers.parse('I POST to "{path}" with:'))
def post_json(pubtest_ctx, http_client, path, docstring):
    send(pubtest_ctx, http_client, "POST", path, docstring.encode(), "application/json")


@when(parsers.parse('I POST to "{path}" with the form:'))
def post_form(pubtest_ctx, http_client, path, datatable):
    fields = {row[0]: row[1] for row in datatable[1:]} if datatable and datatable[0][:2] == ["field", "value"] \
        else {row[0]: row[1] for row in datatable}
    send(pubtest_ctx, http_client, "POST", path, urlencode(fields).encode(), "application/x-www-form-urlencoded")


@when(parsers.re(r'I send "(?P<method>[^"]+)" to "(?P<path>[^"]+)"'))
def send_method(pubtest_ctx, http_client, method, path):
    send(pubtest_ctx, http_client, method, path)


@when(parsers.parse('I send "{method}" to "{path}" with:'))
def send_json(pubtest_ctx, http_client, method, path, docstring):
    send(pubtest_ctx, http_client, method, path, docstring.encode(), "application/json")


@when(parsers.parse('I send "{method}" to "{path}" with the file "{file}"'))
def send_file(pubtest_ctx, http_client, method, path, file):
    """The file's bytes, as they are, with the Content-Type a Given set, or
    application/octet-stream."""
    from .files import at  # noqa: PLC0415
    body = at(pubtest_ctx, file).read_bytes()
    typed = any(k.lower() == "content-type" for k in _headers(pubtest_ctx))
    send(pubtest_ctx, http_client, method, path, body, None if typed else "application/octet-stream")


def _answer(pubtest_ctx):
    assert getattr(pubtest_ctx, "answer", None) is not None, "no request was sent"
    return pubtest_ctx.answer


def _show(answer) -> str:
    return f"{answer.status} {answer.headers}\n{answer.text[:2000]}"


@then(parsers.parse("the answer is {status:d}"))
def answer_is(pubtest_ctx, status):
    answer = _answer(pubtest_ctx)
    assert answer.status == status, _show(answer)


@then(parsers.parse('the answer\'s "{name}" is "{wanted}"'))
def answer_header(pubtest_ctx, name, wanted):
    answer = _answer(pubtest_ctx)
    assert answer.header(name) == wanted, _show(answer)


@then(parsers.parse('the answer has no "{name}"'))
def answer_no_header(pubtest_ctx, name):
    answer = _answer(pubtest_ctx)
    assert answer.header(name) is None, _show(answer)


@then(parsers.parse('the answer includes "{text}" once'))
def answer_includes_once(pubtest_ctx, text):
    answer = _answer(pubtest_ctx)
    assert sum(1 for line in answer.text.splitlines() if text in line) == 1, _show(answer)


@then(parsers.parse('the answer includes "{text}"'))
def answer_includes(pubtest_ctx, text):
    answer = _answer(pubtest_ctx)
    assert text in answer.text, _show(answer)


@then(parsers.parse('the answer does not include "{text}"'))
def answer_excludes(pubtest_ctx, text):
    answer = _answer(pubtest_ctx)
    assert text not in answer.text, _show(answer)


@then("the answer is the JSON:")
def answer_json(pubtest_ctx, docstring):
    answer = _answer(pubtest_ctx)
    assert json.loads(answer.body) == json.loads(docstring), _show(answer)


@then(parsers.parse('the answer redirects to "{path}"'))
def answer_redirects(pubtest_ctx, path):
    answer = _answer(pubtest_ctx)
    assert 300 <= answer.status < 400 and same(answer.header("Location"), path), _show(answer)
