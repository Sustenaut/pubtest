"""Calls to outside services: faults on a scenario's cassette, another
scenario's cassette, and what the calls came to (the record/replay harness,
pubtest.cassettes)."""

from __future__ import annotations

from pytest_bdd import given, then

from .. import cassettes
from . import phrase

# Longer than any operation's timeout: slower than this is no answer.
NEVER = 86400


def tape(pubtest_ctx) -> cassettes.Tape:
    """The scenario's tape; a failure saying how to turn the harness on when it is off."""
    found = getattr(pubtest_ctx, "tape", None)
    assert found is not None, cassettes.OFF
    return found


@given(phrase('the "{name}" integration can\'t be reached'))
def cant_be_reached(pubtest_ctx, name):
    """NAME is a plugin's id, or a prefix: "github" is every github.* plugin."""
    tape(pubtest_ctx).fault(name, "no-answer")


@given(phrase('the "{name}" integration does not answer in time'))
def not_in_time(pubtest_ctx, name):
    tape(pubtest_ctx).fault(name, f"slow {NEVER}")


@given(phrase('the "{name}" integration answers "{request}" with {status:d} and:'))
def answers_with_body(pubtest_ctx, name, request, status, docstring):
    """REQUEST is "METHOD PATH", PATH a pattern in which * is anything."""
    tape(pubtest_ctx).fault(name, f"status {status}", where=request, body=docstring)


@given(phrase('the "{name}" integration answers with {status:d}, then as recorded'))
def answers_then_recorded(pubtest_ctx, name, status):
    tape(pubtest_ctx).fault(name, f"status {status}", nth="first")


@given(phrase('the "{name}" integration answers with what is not JSON'))
def not_json(pubtest_ctx, name):
    tape(pubtest_ctx).fault(name, "malformed")


@given(phrase('the cassette of "{scenario}"'))
def cassette_of(pubtest_ctx, scenario):
    tape(pubtest_ctx).borrow(scenario)


@then(phrase("the Caller slept {seconds} seconds"))
def slept(pubtest_ctx, seconds):
    got = tape(pubtest_ctx).clock.slept
    assert abs(got - float(seconds)) < 1e-9, f"the Caller slept {got:g} seconds"


@then(phrase('"{name}" was called {count:d} times'))
def called(pubtest_ctx, name, count):
    """Each try counts: a call tried three times was called three times."""
    made = [p for p, _ in tape(pubtest_ctx).requests if cassettes.matches_name(name, p)]
    assert len(made) == count, f"{name} was called {len(made)} times: {tape(pubtest_ctx).requests}"
