"""Secrets: values that must never show in anything the action produced."""

from __future__ import annotations

import json

from pytest_bdd import given, then

from ..core import files_in
from . import phrase


@given(phrase('the secret "{text}"'))
def secret(pubtest_ctx, text):
    pubtest_ctx.secrets.append(text)


def produced(pubtest_ctx) -> dict[str, str]:
    """Everything the action produced, by where it went."""
    out: dict[str, str] = {}
    outcome = pubtest_ctx.outcome
    if outcome is not None:
        out["stdout"], out["stderr"] = outcome.stdout, outcome.stderr
        out["the result"] = json.dumps(outcome.value, default=str) if outcome.value is not None else ""
        if outcome.refused is not None:
            out["the refusal"] = outcome.refused.message + repr(outcome.refused.error)
    answer = getattr(pubtest_ctx, "answer", None)
    if answer is not None:
        out["the answer"] = json.dumps(answer.headers) + answer.text
    if pubtest_ctx.directory is not None:
        before = pubtest_ctx.written or {}
        for path, data in files_in(pubtest_ctx.directory).items():
            if before.get(path) != data:
                out[f"the file {path}"] = data.decode("utf-8", "replace")
    standins = getattr(pubtest_ctx, "standins", None)
    if standins is not None:
        # The arguments it gave a program; what it gave one through its
        # environment is deliberately not a leak.
        out["the programs it ran"] = json.dumps(standins.runs())
    for name, fake in getattr(pubtest_ctx, "fakes", {}).items():
        out[f"what it sent {name}"] = json.dumps(fake.requests)
    return out


@then("no secret appears in what it produced")
def no_secret(pubtest_ctx):
    assert pubtest_ctx.secrets, "no secret was given: the step checks the values a Given named"
    leaks = [f"{s!r} in {where}" for where, text in produced(pubtest_ctx).items() for s in pubtest_ctx.secrets if s in text]
    assert not leaks, "a secret appears: " + "; ".join(leaks)
