"""The result: what a scenario's action returned, or the refusal it raised."""

from __future__ import annotations

from typing import Any

import pytest
from pytest_bdd import then

from ..core import dig, includes, matches, same, show
from . import phrase


class Current:
    """The `result` fixture: whatever the context's action came to at the
    moment it is read, so a second When is what later steps see. Its
    attributes are the current Result's."""

    def __init__(self, pubtest_ctx) -> None:
        self._ctx = pubtest_ctx

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ctx.outcome, name)

    def __repr__(self) -> str:
        return f"Current({self._ctx.outcome!r})"


@pytest.fixture
def result(pubtest_ctx) -> Any:
    """What the action came to: the context's current Result, read when a
    step reads it. A suite's step that sets target_fixture="result" takes
    its place with a value of its own."""
    return Current(pubtest_ctx)


def outcome(pubtest_ctx, result: Any) -> Any:
    """What a step that reads the run checks: the context's outcome now,
    unless a suite's own step put something else in the `result` fixture."""
    if isinstance(result, Current):
        assert pubtest_ctx.outcome is not None, "no action was taken: a When leaves the result"
        return pubtest_ctx.outcome
    return result


def _returned(pubtest_ctx) -> Any:
    assert pubtest_ctx.outcome is not None, "no action was taken: a When leaves the result"
    if pubtest_ctx.refused is not None:
        pubtest_ctx.refusal_read = True
        raise AssertionError(f"it was refused: {pubtest_ctx.refused.message!r}") from pubtest_ctx.refused.error
    return pubtest_ctx.result


@then(phrase('the result is "{wanted}"'))
def result_is(pubtest_ctx, wanted):
    got = _returned(pubtest_ctx)
    assert same(got, wanted), f"the result is {show(got)}, not {wanted}"


@then(phrase('the result is not "{wanted}"'))
def result_is_not(pubtest_ctx, wanted):
    got = _returned(pubtest_ctx)
    assert not same(got, wanted), f"the result is {wanted}"


@then("the result is:")
def result_is_docstring(pubtest_ctx, docstring=None, datatable=None):
    """A docstring is the JSON (or text) the result is; a table is a list of
    maps, its header row the keys, each cell compared as a step's value."""
    got = _returned(pubtest_ctx)
    if datatable is not None:
        keys, rows = datatable[0], datatable[1:]
        assert isinstance(got, list) and len(got) == len(rows), f"the result is {show(got)}"
        for item, row in zip(got, rows, strict=True):
            for key, cell in zip(keys, row, strict=True):
                assert same(dig(item, key), cell), f"the result is {show(got)}; {key} is not {cell}"
        return
    assert same(got, docstring), f"the result is {show(got)}, not:\n{docstring}"


@then(phrase('the result includes "{item}"'))
def result_includes(pubtest_ctx, item):
    got = _returned(pubtest_ctx)
    assert includes(got, item), f"the result {show(got)} does not include {item}"


@then(phrase('the result does not include "{item}"'))
def result_excludes(pubtest_ctx, item):
    got = _returned(pubtest_ctx)
    assert not includes(got, item), f"the result {show(got)} includes {item}"


def _at(data: Any, key: str, what: str) -> Any:
    try:
        return dig(data, key)
    except (LookupError, AttributeError, TypeError, ValueError) as e:
        raise AssertionError(f"{what} has no {key}: {show(data)}") from e


@then(phrase('the result\'s "{key}" is "{wanted}"'))
def result_key_is(pubtest_ctx, key, wanted):
    got = _at(_returned(pubtest_ctx), key, "the result")
    assert same(got, wanted), f"the result's {key} is {show(got)}, not {wanted}"


@then(phrase('the result\'s "{key}" includes "{item}"'))
def result_key_includes(pubtest_ctx, key, item):
    got = _at(_returned(pubtest_ctx), key, "the result")
    assert includes(got, item), f"the result's {key} {show(got)} does not include {item}"


@then(phrase('the result\'s "{key}" matches "{pattern}"'))
def result_key_matches(pubtest_ctx, key, pattern):
    got = _at(_returned(pubtest_ctx), key, "the result")
    assert isinstance(got, str), f"the result's {key} is {show(got)}, not text"
    assert matches(pattern, got), f"the result's {key} {got!r} does not match {pattern!r}"


@then(phrase("the result has {count:d} {noun}"))
def result_has(pubtest_ctx, count, noun):
    got = _returned(pubtest_ctx)
    assert len(got) == count, f"the result has {len(got)} {noun}, not {count}: {show(got)}"


@then("the result is empty")
def result_empty(pubtest_ctx):
    got = _returned(pubtest_ctx)
    assert got is None or got in ("", [], {}, ()), f"the result is {show(got)}"


@then(phrase('it is refused, saying "{text}"'))
def refused_saying(pubtest_ctx, text):
    said = _refusal(pubtest_ctx).message or pubtest_ctx.outcome.stderr
    assert text in said, f"it was refused, saying {said!r}"


@then("it is refused")
def refused(pubtest_ctx):
    _refusal(pubtest_ctx)


@then("it is not refused")
def not_refused(pubtest_ctx):
    pubtest_ctx.refusal_read = True
    assert pubtest_ctx.refused is None, f"it was refused, saying {pubtest_ctx.refused.message!r}"


@then(phrase('the result matches "{pattern}"'))
def result_matches(pubtest_ctx, pattern):
    """The result is text, and all of it is the pattern (`*` for anything)."""
    got = _returned(pubtest_ctx)
    assert isinstance(got, str), f"the result is {show(got)}, not text"
    assert matches(pattern, got), f"the result {got!r} does not match {pattern!r}"


def _refusal(pubtest_ctx):
    pubtest_ctx.refusal_read = True
    assert pubtest_ctx.refused is not None, f"it was not refused: the result is {show(pubtest_ctx.result)}"
    return pubtest_ctx.refused


@then(phrase('the refusal is a "{name}"'))
def refusal_is_a(pubtest_ctx, name):
    """The refusal's class, or a class it derives from, is NAME: its own
    name, or its module's and its own (`builtins.KeyError`)."""
    error = _refusal(pubtest_ctx).error
    classes = type(error).__mro__
    names = {c.__name__ for c in classes} | {f"{c.__module__}.{c.__qualname__}" for c in classes}
    assert name in names, f"the refusal is a {' < '.join(c.__qualname__ for c in classes)}, not a {name}"


@then(phrase('the refusal\'s "{key}" is "{wanted}"'))
def refusal_key_is(pubtest_ctx, key, wanted):
    """The value at the dotted key K of the refusal's attributes; `message`
    is its message."""
    refused = _refusal(pubtest_ctx)
    got = refused.message if key == "message" else _at(refused.error, key, "the refusal")
    assert same(got, wanted), f"the refusal's {key} is {show(got)}, not {wanted}"
