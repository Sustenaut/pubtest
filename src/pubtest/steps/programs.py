"""Programs: the one under test, run as a person runs it."""

from __future__ import annotations

import os
import shlex
from typing import Any

import pytest
from pytest_bdd import given, parsers, then, when

from ..core import Completed, Result, program


def _text(result: Any, stream: str) -> str:
    raw = getattr(result, stream)
    return raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw


def _code(result: Any) -> int:
    code = getattr(result, "code", None)
    return result.returncode if code is None else code


def _show(result: Any) -> str:
    if isinstance(result, (Completed, Result)):
        return result.describe()
    return f"exit {_code(result)}\nstdout: {_text(result, 'stdout')!r}\nstderr: {_text(result, 'stderr')!r}"


@given(parsers.parse('the program under test is "{name}"'))
def under_test(ctx, name):
    try:
        ctx.programs = {**getattr(ctx, "programs", {}), name: str(program(name))}
    except LookupError as e:
        pytest.fail(str(e))


def run_command(ctx, command: str, stdin: str | None) -> Result:
    """CMD's first word is the program under test of that name, from its
    _BIN_DIR, when a Given named it; otherwise it is found on PATH, stand-ins
    first. It runs for at most 120 seconds."""
    from ..plugin import run_program  # noqa: PLC0415
    argv = shlex.split(command)
    argv[0] = getattr(ctx, "programs", {}).get(argv[0], argv[0])
    env = {}
    if getattr(ctx, "standins", None) is not None:
        env["PATH"] = ctx.standins.path()
    ctx.acting()
    done = run_program(argv, stdin, ctx.directory or os.getcwd(), env, 120)
    return ctx.ran(Result(code=done.code, stdout=done.stdout, stderr=done.stderr, argv=done.argv))


@when(parsers.parse('I run "{command}"'), target_fixture="result")
def i_run(ctx, command):
    return run_command(ctx, command, None)


@when(parsers.parse('I run "{command}" with the input:'), target_fixture="result")
def i_run_with_input(ctx, command, docstring):
    return run_command(ctx, command, docstring + "\n")


def _read(ctx) -> None:
    """A step that reads the exit code reads a refusal too."""
    ctx.refusal_read = True


@then("it succeeds")
def it_succeeds(ctx, result):
    _read(ctx)
    assert _code(result) == 0, _show(result)


@then("it fails")
def it_fails(ctx, result):
    _read(ctx)
    assert _code(result) != 0, _show(result)


@then(parsers.parse("the exit code is {code:d}"))
def exit_code_is(ctx, result, code):
    _read(ctx)
    assert _code(result) == code, _show(result)


@then(parsers.parse('it prints "{text}"'))
def it_prints(result, text):
    assert text in _text(result, "stdout"), _show(result)


@then(parsers.parse('it does not print "{text}"'))
def it_does_not_print(result, text):
    assert text not in _text(result, "stdout"), _show(result)


@then("it prints:")
def it_prints_exactly(result, docstring):
    assert _text(result, "stdout").removesuffix("\n") == docstring.removesuffix("\n"), _show(result)


@then("stdout is empty")
def stdout_is_empty(result):
    assert _text(result, "stdout") == "", _show(result)


@then(parsers.parse('stderr mentions "{text}"'))
def stderr_mentions(result, text):
    assert text in _text(result, "stderr"), _show(result)


@then(parsers.parse('stderr does not mention "{text}"'))
def stderr_does_not_mention(result, text):
    assert text not in _text(result, "stderr"), _show(result)
