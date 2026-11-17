"""The result: what a scenario's action returned, or the refusal it raised."""

from __future__ import annotations

from typing import Any

import pytest
from pytest_bdd import parsers, then

from ..core import dig, includes, matches, same, show


@pytest.fixture
def result(pubtest_ctx) -> Any:
    """What the action came to (a Result); a suite's step that sets
    target_fixture="result" takes its place."""
    return pubtest_ctx.outcome


def _returned(pubtest_ctx) -> Any:
    assert pubtest_ctx.outcome is not None, "no action was taken: a When leaves the result"
    if pubtest_ctx.refused is not None:
        pubtest_ctx.refusal_read = True
        raise AssertionError(f"it was refused: {pubtest_ctx.refused.message!r}") from pubtest_ctx.refused.error
    return pubtest_ctx.result


@then(parsers.parse('the result is "{wanted}"'))
def result_is(pubtest_ctx, wanted):
    got = _returned(pubtest_ctx)
    assert same(got, wanted), f"the result is {show(got)}, not {wanted}"


@then(parsers.parse('the result is not "{wanted}"'))
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


@then(parsers.parse('the result includes "{item}"'))
def result_includes(pubtest_ctx, item):
    got = _returned(pubtest_ctx)
    assert includes(got, item), f"the result {show(got)} does not include {item}"


@then(parsers.parse('the result does not include "{item}"'))
def result_excludes(pubtest_ctx, item):
    got = _returned(pubtest_ctx)
    assert not includes(got, item), f"the result {show(got)} includes {item}"


@then(parsers.parse('the result\'s "{key}" is "{wanted}"'))
def result_key_is(pubtest_ctx, key, wanted):
    got = dig(_returned(pubtest_ctx), key)
    assert same(got, wanted), f"the result's {key} is {show(got)}, not {wanted}"


@then(parsers.parse("the result has {count:d} {noun}"))
def result_has(pubtest_ctx, count, noun):
    got = _returned(pubtest_ctx)
    assert len(got) == count, f"the result has {len(got)} {noun}, not {count}: {show(got)}"


@then("the result is empty")
def result_empty(pubtest_ctx):
    got = _returned(pubtest_ctx)
    assert got is None or got in ("", [], {}, ()), f"the result is {show(got)}"


@then(parsers.parse('it is refused, saying "{text}"'))
def refused_saying(pubtest_ctx, text):
    pubtest_ctx.refusal_read = True
    assert pubtest_ctx.refused is not None, f"it was not refused: the result is {show(pubtest_ctx.result)}"
    said = pubtest_ctx.refused.message or pubtest_ctx.outcome.stderr
    assert text in said, f"it was refused, saying {said!r}"


@then("it is refused")
def refused(pubtest_ctx):
    pubtest_ctx.refusal_read = True
    assert pubtest_ctx.refused is not None, f"it was not refused: the result is {show(pubtest_ctx.result)}"


@then("it is not refused")
def not_refused(pubtest_ctx):
    pubtest_ctx.refusal_read = True
    assert pubtest_ctx.refused is None, f"it was refused, saying {pubtest_ctx.refused.message!r}"


@then(parsers.parse('the result matches "{pattern}"'))
def result_matches(pubtest_ctx, pattern):
    """The result is text, and all of it is the pattern (`*` for anything)."""
    got = _returned(pubtest_ctx)
    assert isinstance(got, str), f"the result is {show(got)}, not text"
    assert matches(pattern, got), f"the result {got!r} does not match {pattern!r}"
