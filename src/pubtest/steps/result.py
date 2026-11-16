"""The result: what a scenario's action returned, or the refusal it raised."""

from __future__ import annotations

from typing import Any

import pytest
from pytest_bdd import parsers, then

from ..core import dig, includes, same, show


@pytest.fixture
def result(ctx) -> Any:
    """What the action came to (a Result); a suite's step that sets
    target_fixture="result" takes its place."""
    return ctx.outcome


def _returned(ctx) -> Any:
    assert ctx.outcome is not None, "no action was taken: a When leaves the result"
    if ctx.refused is not None:
        ctx.refusal_read = True
        raise AssertionError(f"it was refused: {ctx.refused.message!r}") from ctx.refused.error
    return ctx.result


@then(parsers.parse('the result is "{wanted}"'))
def result_is(ctx, wanted):
    got = _returned(ctx)
    assert same(got, wanted), f"the result is {show(got)}, not {wanted}"


@then(parsers.parse('the result is not "{wanted}"'))
def result_is_not(ctx, wanted):
    got = _returned(ctx)
    assert not same(got, wanted), f"the result is {wanted}"


@then("the result is:")
def result_is_docstring(ctx, docstring=None, datatable=None):
    """A docstring is the JSON (or text) the result is; a table is a list of
    maps, its header row the keys, each cell compared as a step's value."""
    got = _returned(ctx)
    if datatable is not None:
        keys, rows = datatable[0], datatable[1:]
        assert isinstance(got, list) and len(got) == len(rows), f"the result is {show(got)}"
        for item, row in zip(got, rows, strict=True):
            for key, cell in zip(keys, row, strict=True):
                assert same(dig(item, key), cell), f"the result is {show(got)}; {key} is not {cell}"
        return
    assert same(got, docstring), f"the result is {show(got)}, not:\n{docstring}"


@then(parsers.parse('the result includes "{item}"'))
def result_includes(ctx, item):
    got = _returned(ctx)
    assert includes(got, item), f"the result {show(got)} does not include {item}"


@then(parsers.parse('the result does not include "{item}"'))
def result_excludes(ctx, item):
    got = _returned(ctx)
    assert not includes(got, item), f"the result {show(got)} includes {item}"


@then(parsers.parse('the result\'s "{key}" is "{wanted}"'))
def result_key_is(ctx, key, wanted):
    got = dig(_returned(ctx), key)
    assert same(got, wanted), f"the result's {key} is {show(got)}, not {wanted}"


@then(parsers.parse("the result has {count:d} {noun}"))
def result_has(ctx, count, noun):
    got = _returned(ctx)
    assert len(got) == count, f"the result has {len(got)} {noun}, not {count}: {show(got)}"


@then("the result is empty")
def result_empty(ctx):
    got = _returned(ctx)
    assert got is None or got in ("", [], {}, ()), f"the result is {show(got)}"


@then(parsers.parse('it is refused, saying "{text}"'))
def refused_saying(ctx, text):
    ctx.refusal_read = True
    assert ctx.refused is not None, f"it was not refused: the result is {show(ctx.result)}"
    said = ctx.refused.message or ctx.outcome.stderr
    assert text in said, f"it was refused, saying {said!r}"


@then("it is refused")
def refused(ctx):
    ctx.refusal_read = True
    assert ctx.refused is not None, f"it was not refused: the result is {show(ctx.result)}"


@then("it is not refused")
def not_refused(ctx):
    ctx.refusal_read = True
    assert ctx.refused is None, f"it was refused, saying {ctx.refused.message!r}"
