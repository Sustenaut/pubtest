"""Files in the scenario's scratch directory."""

from __future__ import annotations

import json
import os
import shutil
import stat
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from ..core import dig, files_in, repository, same, show, yaml_documents


def at(pubtest_ctx, path: str) -> Path:
    """`path`, in the scratch directory when there is one."""
    return (pubtest_ctx.directory or Path.cwd()) / path


@given("a scratch directory")
def scratch_directory(pubtest_ctx, tmp_path, monkeypatch):
    pubtest_ctx.directory = tmp_path / "scratch"
    pubtest_ctx.directory.mkdir()
    monkeypatch.chdir(pubtest_ctx.directory)


def _write(pubtest_ctx, path: str, text: str) -> None:
    target = at(pubtest_ctx, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


@given(parsers.parse('a file "{path}" holding "{text}"'))
def holds_line(pubtest_ctx, path, text):
    _write(pubtest_ctx, path, text + "\n")


@given(parsers.parse('a file "{path}" holding:'))
def holds_text(pubtest_ctx, path, docstring):
    _write(pubtest_ctx, path, docstring + "\n")


@pytest.fixture(scope="session")
def pubtest_repository(request) -> Path:
    """The repository the suite runs in, which `copied from` paths are in."""
    return repository(Path(request.config.invocation_params.dir))


@given(parsers.parse('a file "{path}" copied from "{source}"'))
def copied(pubtest_ctx, pubtest_repository, path, source):
    origin = (pubtest_repository / source).resolve()
    if Path(source).is_absolute() or not origin.is_relative_to(pubtest_repository.resolve()):
        raise AssertionError(f"{source} is not in the repository: copy only the repository's own files")
    assert origin.exists(), f"the repository has no {source}"
    target = at(pubtest_ctx, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if origin.is_dir():
        shutil.copytree(origin, target, dirs_exist_ok=True)
    else:
        shutil.copyfile(origin, target)


@given(parsers.parse('the file "{path}" is executable'))
def executable(pubtest_ctx, path):
    target = at(pubtest_ctx, path)
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@given(parsers.parse('the file "{path}" is removed'))
def removed(pubtest_ctx, path):
    target = at(pubtest_ctx, path)
    shutil.rmtree(target) if target.is_dir() else target.unlink()


@when(parsers.parse('the file "{path}" changes to:'))
def changes(pubtest_ctx, path, docstring):
    _write(pubtest_ctx, path, docstring + "\n")


@then(parsers.parse('the file "{path}" exists'))
def exists(pubtest_ctx, path):
    assert at(pubtest_ctx, path).exists(), f"there is no {path}"


@then(parsers.parse('the file "{path}" does not exist'))
def not_exists(pubtest_ctx, path):
    assert not at(pubtest_ctx, path).exists(), f"{path} exists"


def _text(pubtest_ctx, path: str) -> str:
    target = at(pubtest_ctx, path)
    assert target.is_file(), f"there is no {path}"
    return target.read_text(encoding="utf-8")


@then(parsers.parse('the file "{path}" holds "{text}"'))
def file_holds_line(pubtest_ctx, path, text):
    got = _text(pubtest_ctx, path)
    assert got.removesuffix("\n") == text, f"{path} holds {got!r}"


@then(parsers.parse('the file "{path}" holds:'))
def file_holds_text(pubtest_ctx, path, docstring):
    got = _text(pubtest_ctx, path)
    assert got.removesuffix("\n") == docstring.removesuffix("\n"), f"{path} holds:\n{got}"


@then(parsers.parse('the file "{path}" includes "{text}" once'))
def file_includes_once(pubtest_ctx, path, text):
    lines = [line for line in _text(pubtest_ctx, path).splitlines() if text in line]
    assert len(lines) == 1, f"{path} has {len(lines)} lines with {text!r}"


@then(parsers.parse('the file "{path}" includes "{text}"'))
def file_includes(pubtest_ctx, path, text):
    assert text in _text(pubtest_ctx, path), f"{path} does not include {text!r}"


@then(parsers.parse('the file "{path}" does not include "{text}"'))
def file_excludes(pubtest_ctx, path, text):
    assert text not in _text(pubtest_ctx, path), f"{path} includes {text!r}"


@then(parsers.parse('the JSON in "{path}" is:'))
def json_is(pubtest_ctx, path, docstring):
    got = json.loads(_text(pubtest_ctx, path))
    assert got == json.loads(docstring), f"{path} holds {show(got)}"


@then(parsers.parse('the JSON in "{path}" has "{key}" equal to "{wanted}"'))
def json_key(pubtest_ctx, path, key, wanted):
    got = dig(json.loads(_text(pubtest_ctx, path)), key)
    assert same(got, wanted), f"{path}'s {key} is {show(got)}, not {wanted}"


@then("nothing was written")
def nothing_written(pubtest_ctx):
    assert pubtest_ctx.directory is not None, "nothing was written needs a scratch directory"
    assert pubtest_ctx.written is not None, "nothing was written needs a When: it compares with the directory before it"
    before, after = pubtest_ctx.written, files_in(pubtest_ctx.directory)
    changed = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
    assert not changed, f"written: {', '.join(changed)}"




@then(parsers.parse('the file "{path}" can be run'))
def can_be_run(pubtest_ctx, path):
    target = at(pubtest_ctx, path)
    assert target.is_file(), f"there is no {path}"
    assert os.access(target, os.X_OK), f"{path} is not executable"


@then(parsers.parse('the directory "{path}" holds:'))
def directory_holds(pubtest_ctx, path, docstring):
    """The names in the directory, one a line, in name order; a directory's
    ends with a slash."""
    target = at(pubtest_ctx, path)
    assert target.is_dir(), f"there is no directory {path}"
    names = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
    want = [line.strip() for line in docstring.splitlines() if line.strip()]
    assert names == want, f"{path} holds:\n" + "\n".join(names)


@then(parsers.parse('the YAML in "{path}" is:'))
def yaml_is(pubtest_ctx, path, docstring):
    got, want = yaml_documents(_text(pubtest_ctx, path)), yaml_documents(docstring)
    assert got == want, f"{path} holds {show(got)}"


@then(parsers.parse('the YAML in "{path}" has "{key}" equal to "{wanted}"'))
def yaml_key(pubtest_ctx, path, key, wanted):
    got = dig(yaml_documents(_text(pubtest_ctx, path)), key)
    assert same(got, wanted), f"{path}'s {key} is {show(got)}, not {wanted}"
