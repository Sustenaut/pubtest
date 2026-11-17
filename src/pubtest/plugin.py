"""The pytest plugin every Sustenaut suite loads (the `pytest11` entry point).

It gives a suite pubtest's steps (GRAMMAR.md), and:

- `ctx`: the scenario's context, its result and refusal, and the cleanups
  that run when it ends, in reverse, passed or failed;
- `binary(name)`: a program under test, from `<NAME>_BIN_DIR`, never from
  PATH, so another implementation runs the suite by setting one variable;
- `run(...)`: run a program and capture what it did as a `Completed`;
- markers for every `@tag` the feature files carry, so `--strict-markers`
  catches a typo without each tag registered by hand;
- Hypothesis's examples per property from `PUBRULES_FUZZ_RUNS`, which CI sets.

A suite's own step with the same text takes precedence over these.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from .core import Completed, Context, Result, bin_var, program

__all__ = ["Completed", "Context", "Result", "bin_var"]

pytest_plugins = [
    "pubtest.steps.result",
    "pubtest.steps.files",
    "pubtest.steps.environment",
    "pubtest.steps.programs",
    "pubtest.steps.standins",
    "pubtest.steps.http",
    "pubtest.steps.fakes",
    "pubtest.steps.secrets",
    "pubtest.steps.git",
]


@pytest.fixture
def ctx() -> Any:
    context = Context()
    yield context
    try:
        unread = context.unread_refusal()
        if unread is not None:
            raise AssertionError(f"the action was refused, and no step read it: {unread!r}") from unread
    finally:
        context.close()


@pytest.fixture(scope="session")
def binary() -> Callable[..., Path]:
    """`binary(name, var=None)`: the path of a program under test."""

    def resolve(name: str, var: str | None = None) -> Path:
        try:
            return program(name, var)
        except LookupError as e:
            pytest.fail(str(e))

    return resolve


def run_program(argv: list[str], stdin: bytes | str | None, cwd: str | os.PathLike[str],
                env: Mapping[str, str | None] | None, timeout: float | None) -> Completed:
    merged = dict(os.environ)
    for key, val in (env or {}).items():
        if val is None:
            merged.pop(key, None)
        else:
            merged[key] = val
    if isinstance(stdin, str):
        stdin = stdin.encode()
    proc = subprocess.run(argv, input=stdin, capture_output=True, cwd=cwd, env=merged, timeout=timeout,
                          check=False)
    return Completed(argv, proc.returncode, proc.stdout, proc.stderr)


@pytest.fixture
def run(tmp_path: Path) -> Callable[..., Completed]:
    """`run(program, *args, stdin=None, cwd=tmp_path, env=None)` -> Completed.

    `env` is merged over the current environment; a value of None removes
    that variable.
    """

    def runner(prog: str | os.PathLike[str], *args: str | os.PathLike[str], stdin: bytes | str | None = None,
               cwd: str | os.PathLike[str] | None = None, env: Mapping[str, str | None] | None = None,
               timeout: float | None = 120) -> Completed:
        return run_program([str(prog), *(str(a) for a in args)], stdin, cwd or tmp_path, env, timeout)

    return runner


def _features(config: pytest.Config) -> Path:
    base = config.inipath.parent if config.inipath else config.rootpath
    try:
        configured = config.getini("bdd_features_base_dir")
    except ValueError:
        configured = ""
    return base / configured if configured else base


def _hypothesis_runs() -> None:
    """Load a Hypothesis profile running PUBRULES_FUZZ_RUNS examples per
    property, with no deadline: on a shared CI runner timing is noise."""
    raw = os.environ.get("PUBRULES_FUZZ_RUNS", "")
    if not raw:
        return
    if not raw.isdigit() or int(raw) < 1:
        raise pytest.UsageError(f"PUBRULES_FUZZ_RUNS must be a positive whole number, not {raw!r}")
    try:
        from hypothesis import settings  # noqa: PLC0415
    except ImportError:
        return
    settings.register_profile("pubrules", max_examples=int(raw), deadline=None, print_blob=True)
    settings.load_profile("pubrules")


def pytest_configure(config: pytest.Config) -> None:
    _hypothesis_runs()
    root = _features(config)
    tags: set[str] = set()
    if root.is_dir():
        for path in root.rglob("*.feature"):
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("@"):
                    tags.update(t[1:] for t in stripped.split() if t.startswith("@"))
    for tag in sorted(tags):
        config.addinivalue_line("markers", f"{tag}: a feature-file tag")
