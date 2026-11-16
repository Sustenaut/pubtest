"""Files in the scenario's scratch directory."""

from __future__ import annotations

import json
import shutil
import stat
from pathlib import Path

from pytest_bdd import given, parsers, then, when

from ..core import dig, files_in, same, show


def at(ctx, path: str) -> Path:
    """`path`, in the scratch directory when there is one."""
    return (ctx.directory or Path.cwd()) / path


@given("a scratch directory")
def scratch_directory(ctx, tmp_path, monkeypatch):
    ctx.directory = tmp_path / "scratch"
    ctx.directory.mkdir()
    monkeypatch.chdir(ctx.directory)


def _write(ctx, path: str, text: str) -> None:
    target = at(ctx, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


@given(parsers.parse('a file "{path}" holding "{text}"'))
def holds_line(ctx, path, text):
    _write(ctx, path, text + "\n")


@given(parsers.parse('a file "{path}" holding:'))
def holds_text(ctx, path, docstring):
    _write(ctx, path, docstring + "\n")


@given(parsers.parse('the file "{path}" is executable'))
def executable(ctx, path):
    target = at(ctx, path)
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@given(parsers.parse('the file "{path}" is removed'))
def removed(ctx, path):
    target = at(ctx, path)
    shutil.rmtree(target) if target.is_dir() else target.unlink()


@when(parsers.parse('the file "{path}" changes to:'))
def changes(ctx, path, docstring):
    _write(ctx, path, docstring + "\n")


@then(parsers.parse('the file "{path}" exists'))
def exists(ctx, path):
    assert at(ctx, path).exists(), f"there is no {path}"


@then(parsers.parse('the file "{path}" does not exist'))
def not_exists(ctx, path):
    assert not at(ctx, path).exists(), f"{path} exists"


def _text(ctx, path: str) -> str:
    target = at(ctx, path)
    assert target.is_file(), f"there is no {path}"
    return target.read_text(encoding="utf-8")


@then(parsers.parse('the file "{path}" holds "{text}"'))
def file_holds_line(ctx, path, text):
    got = _text(ctx, path)
    assert got.removesuffix("\n") == text, f"{path} holds {got!r}"


@then(parsers.parse('the file "{path}" holds:'))
def file_holds_text(ctx, path, docstring):
    got = _text(ctx, path)
    assert got.removesuffix("\n") == docstring.removesuffix("\n"), f"{path} holds:\n{got}"


@then(parsers.parse('the file "{path}" includes "{text}" once'))
def file_includes_once(ctx, path, text):
    lines = [line for line in _text(ctx, path).splitlines() if text in line]
    assert len(lines) == 1, f"{path} has {len(lines)} lines with {text!r}"


@then(parsers.parse('the file "{path}" includes "{text}"'))
def file_includes(ctx, path, text):
    assert text in _text(ctx, path), f"{path} does not include {text!r}"


@then(parsers.parse('the file "{path}" does not include "{text}"'))
def file_excludes(ctx, path, text):
    assert text not in _text(ctx, path), f"{path} includes {text!r}"


@then(parsers.parse('the JSON in "{path}" is:'))
def json_is(ctx, path, docstring):
    got = json.loads(_text(ctx, path))
    assert got == json.loads(docstring), f"{path} holds {show(got)}"


@then(parsers.parse('the JSON in "{path}" has "{key}" equal to "{wanted}"'))
def json_key(ctx, path, key, wanted):
    got = dig(json.loads(_text(ctx, path)), key)
    assert same(got, wanted), f"{path}'s {key} is {show(got)}, not {wanted}"


@then("nothing was written")
def nothing_written(ctx):
    assert ctx.directory is not None, "nothing was written needs a scratch directory"
    assert ctx.written is not None, "nothing was written needs a When: it compares with the directory before it"
    before, after = ctx.written, files_in(ctx.directory)
    changed = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
    assert not changed, f"written: {', '.join(changed)}"


