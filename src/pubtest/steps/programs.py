"""Programs: the one under test, run as a person runs it."""

from __future__ import annotations

import json
import os
import shlex
from typing import Any

import pytest
from pytest_bdd import given, then, when

from ..core import Completed, Result, dig, matches, program, same, show
from . import phrase
from .result import Current, outcome


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


@given(phrase('the program under test is "{name}"'))
def under_test(pubtest_ctx, name):
    try:
        pubtest_ctx.programs = {**getattr(pubtest_ctx, "programs", {}), name: str(program(name))}
    except LookupError as e:
        pytest.fail(str(e))


def run_command(pubtest_ctx, command: str, stdin: str | None) -> Result:
    """CMD's first word is the program under test of that name, from its
    _BIN_DIR, when a Given named it; otherwise it is found on PATH, stand-ins
    first. It runs for at most 120 seconds."""
    from ..plugin import run_program  # noqa: PLC0415
    argv = shlex.split(command)
    argv[0] = getattr(pubtest_ctx, "programs", {}).get(argv[0], argv[0])
    env = {}
    if getattr(pubtest_ctx, "standins", None) is not None:
        env["PATH"] = pubtest_ctx.standins.path()
    pubtest_ctx.acting()
    done = run_program(argv, stdin, pubtest_ctx.directory or os.getcwd(), env, 120)
    return pubtest_ctx.ran(Result(code=done.code, stdout=done.stdout, stderr=done.stderr, argv=done.argv))


# The result fixture is the context's own again, after a suite's step that
# set it: later steps read this run.
@when(phrase('I run "{command}"'), target_fixture="result")
def i_run(pubtest_ctx, command):
    run_command(pubtest_ctx, command, None)
    return Current(pubtest_ctx)


@when(phrase('I run "{command}" with the input:'), target_fixture="result")
def i_run_with_input(pubtest_ctx, command, docstring):
    run_command(pubtest_ctx, command, docstring + "\n")
    return Current(pubtest_ctx)


def _read(pubtest_ctx) -> None:
    """A step that reads the exit code reads a refusal too."""
    pubtest_ctx.refusal_read = True


def _lines(run: Any, stream: str) -> list[str]:
    return _text(run, stream).splitlines()


@then("it succeeds")
def it_succeeds(pubtest_ctx, result):
    _read(pubtest_ctx)
    run = outcome(pubtest_ctx, result)
    assert _code(run) == 0, _show(run)


@then("it fails")
def it_fails(pubtest_ctx, result):
    _read(pubtest_ctx)
    run = outcome(pubtest_ctx, result)
    assert _code(run) != 0, _show(run)


@then(phrase("the exit code is {code:d}"))
def exit_code_is(pubtest_ctx, result, code):
    _read(pubtest_ctx)
    run = outcome(pubtest_ctx, result)
    assert _code(run) == code, _show(run)


@then(phrase('it prints "{text}"'))
def it_prints(pubtest_ctx, result, text):
    run = outcome(pubtest_ctx, result)
    assert text in _text(run, "stdout"), _show(run)


@then(phrase('it does not print "{text}"'))
def it_does_not_print(pubtest_ctx, result, text):
    run = outcome(pubtest_ctx, result)
    assert text not in _text(run, "stdout"), _show(run)


@then("it prints:")
def it_prints_exactly(pubtest_ctx, result, docstring):
    run = outcome(pubtest_ctx, result)
    assert _text(run, "stdout").removesuffix("\n") == docstring.removesuffix("\n"), _show(run)


@then("stdout is empty")
def stdout_is_empty(pubtest_ctx, result):
    run = outcome(pubtest_ctx, result)
    assert _text(run, "stdout") == "", _show(run)


@then("stderr is empty")
def stderr_is_empty(pubtest_ctx, result):
    run = outcome(pubtest_ctx, result)
    assert _text(run, "stderr") == "", _show(run)


@then(phrase('stderr mentions "{text}"'))
def stderr_mentions(pubtest_ctx, result, text):
    run = outcome(pubtest_ctx, result)
    assert text in _text(run, "stderr"), _show(run)


@then(phrase('stderr does not mention "{text}"'))
def stderr_does_not_mention(pubtest_ctx, result, text):
    run = outcome(pubtest_ctx, result)
    assert text not in _text(run, "stderr"), _show(run)


def _printed_json(run: Any) -> Any:
    try:
        return json.loads(_text(run, "stdout"))
    except ValueError as e:
        raise AssertionError(f"it printed no JSON\n{_show(run)}") from e


@then("it prints the JSON:")
def it_prints_json(pubtest_ctx, result, docstring):
    got = _printed_json(outcome(pubtest_ctx, result))
    assert same(got, docstring), f"it printed {show(got)}, not:\n{docstring}"


@then(phrase('the JSON it prints has "{key}" equal to "{wanted}"'))
def printed_json_key(pubtest_ctx, result, key, wanted):
    got = dig(_printed_json(outcome(pubtest_ctx, result)), key)
    assert same(got, wanted), f"the {key} it printed is {show(got)}, not {wanted}"


@then(phrase('it prints a line matching "{pattern}"'))
def prints_line_matching(pubtest_ctx, result, pattern):
    run = outcome(pubtest_ctx, result)
    assert any(matches(pattern, line) for line in _lines(run, "stdout")), f"no line matches {pattern!r}\n{_show(run)}"


@then(phrase('it prints no line matching "{pattern}"'))
def prints_no_line_matching(pubtest_ctx, result, pattern):
    run = outcome(pubtest_ctx, result)
    found = [line for line in _lines(run, "stdout") if matches(pattern, line)]
    assert not found, f"lines match {pattern!r}: {found}\n{_show(run)}"


@then(phrase('stderr has a line matching "{pattern}"'))
def stderr_line_matching(pubtest_ctx, result, pattern):
    run = outcome(pubtest_ctx, result)
    assert any(matches(pattern, line) for line in _lines(run, "stderr")), \
        f"no line of stderr matches {pattern!r}\n{_show(run)}"


@then(phrase('stderr has no line matching "{pattern}"'))
def stderr_no_line_matching(pubtest_ctx, result, pattern):
    run = outcome(pubtest_ctx, result)
    found = [line for line in _lines(run, "stderr") if matches(pattern, line)]
    assert not found, f"lines of stderr match {pattern!r}: {found}\n{_show(run)}"
