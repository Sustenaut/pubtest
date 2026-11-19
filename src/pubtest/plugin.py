"""The pytest plugin every Sustenaut suite loads (the `pytest11` entry point).

It gives a suite pubtest's steps (GRAMMAR.md), and:

- `ctx`: the scenario's context, its result and refusal, and the cleanups
  that run when it ends, in reverse, passed or failed;
- `binary(name)`: a program under test, from `<NAME>_BIN_DIR`, never from
  PATH, so another implementation runs the suite by setting one variable;
- `run(...)`: run a program and capture what it did as a `Completed`;
- markers for every `@tag` the feature files carry, so `--strict-markers`
  catches a typo without each tag registered by hand;
- Hypothesis's examples per property from `PUBRULES_FUZZ_RUNS`, which CI sets;
- record and replay (`pubtest.cassettes`): a cassette per scenario for the
  calls it makes through integrations, when integrations is installed and the
  repository turns cassettes on, and the test customers packages register in
  the `pubtest.customers` entry point group.

A suite's own step with the same text takes precedence over these.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from . import cassettes
from .core import Completed, Context, Result, bin_var, program, repository

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
    "pubtest.steps.integrations",
]

# The test customers packages register (`pubtest.customers`), by name.
CUSTOMERS: dict[str, Any] = {}


def _finish(context: Context) -> None:
    try:
        unread = context.unread_refusal()
        if unread is not None:
            raise AssertionError(f"the action was refused, and no step read it: {unread!r}") from unread
    finally:
        context.close()


@pytest.fixture
def ctx() -> Any:
    """The scenario's context, which a suite's own steps reach as `ctx`. A
    suite may replace it with a fixture of its own; pubtest's steps then keep
    theirs apart (`pubtest_ctx`)."""
    context = Context()
    yield context
    _finish(context)


@pytest.fixture
def pubtest_ctx(request) -> Any:
    """The context pubtest's own steps use: the suite's `ctx` when it is
    pubtest's, and otherwise one of their own, so a suite whose `ctx` is
    something else (a dict, say) loses none of the steps."""
    suite = request.getfixturevalue("ctx")
    if isinstance(suite, Context):
        yield suite
        return
    context = Context()
    yield context
    _finish(context)


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


def _customers(config: pytest.Config) -> None:
    """Each `pubtest.customers` entry point: a module (or object) with a `name`,
    `setup(tape) -> {name: real name}` and `cleanup(tape, names)`, both for record
    mode only, and the steps of its own, which load as a pytest plugin does."""
    from importlib.metadata import entry_points  # noqa: PLC0415
    for point in entry_points(group="pubtest.customers"):
        customer = point.load()
        CUSTOMERS[getattr(customer, "name", point.name)] = customer
        if not config.pluginmanager.is_registered(customer):
            config.pluginmanager.register(customer, f"pubtest-customer-{point.name}")


def pytest_configure(config: pytest.Config) -> None:
    _hypothesis_runs()
    _customers(config)
    found = cassettes.settings(repository(Path(str(config.rootpath))))
    try:
        cassettes.start_session(found)
    except LookupError as e:
        raise pytest.UsageError(str(e)) from None
    config.stash[_SETTINGS] = found
    root = _features(config)
    tags: set[str] = set()
    if root.is_dir():
        for path in root.rglob("*.feature"):
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("@"):
                    tags.update(t[1:] for t in stripped.split() if t.startswith("@") and not
                                t.startswith("@cassette:"))
    for tag in sorted(tags):
        config.addinivalue_line("markers", f"{tag}: a feature-file tag")


# --- record and replay -----------------------------------------------------------

_SETTINGS = pytest.StashKey[cassettes.Settings]()
_TAPE = pytest.StashKey[cassettes.Tape]()


def _scenario(item: Any) -> cassettes.Scenario | None:
    """The scenario a test item runs, as a cassette names it."""
    template = getattr(getattr(item, "function", None), "__scenario__", None)
    if template is None:
        return None
    callspec = getattr(item, "callspec", None)
    index = callspec.indices.get("_pytest_bdd_example") if callspec is not None else None
    row = index + 1 if index is not None and template.examples else None
    return cassettes.Scenario(Path(template.feature.filename).name, template.name, row)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """With PUBTEST_ONLY (`pubtest record`), only the scenarios it names run."""
    if cassettes.only() is None:
        return
    keep, drop = [], []
    for item in items:
        scenario = _scenario(item)
        (keep if scenario is not None and cassettes.selected(scenario) else drop).append(item)
    if drop:
        config.hook.pytest_deselected(items=drop)
        items[:] = keep


@pytest.hookimpl(tryfirst=True)
def pytest_bdd_apply_tag(tag: str, function: Any) -> Any:
    """@cassette:PATH says which cassette a scenario replays: not a marker."""
    return function if tag.startswith("cassette:") else None


def pytest_bdd_before_scenario(request: pytest.FixtureRequest, feature: Any, scenario: Any) -> None:
    found = request.config.stash.get(_SETTINGS, None)
    if found is None or not found.active:
        return
    named = _scenario(request.node)
    if named is None:
        return
    text = cassettes.text_hash([(s.name, s.docstring, [list(map(str, r)) for r in s.datatable.raw()]
                                 if s.datatable else None) for s in scenario.steps])
    tape = cassettes.Tape(found, named, set(scenario.tags) | set(feature.tags), text)
    tape.customers = CUSTOMERS
    tape.begin()
    request.node.stash[_TAPE] = tape
    request.getfixturevalue("pubtest_ctx").tape = tape


def pytest_bdd_before_step(request: Any, feature: Any, scenario: Any, step: Any, step_func: Any) -> None:
    held = request.node.stash.get(_TAPE, None)
    if held is not None:
        held.step(step_func)


def pytest_bdd_step_error(request: Any, feature: Any, scenario: Any, step: Any, step_func: Any,
                          step_func_args: Any, exception: Any) -> None:
    held = request.node.stash.get(_TAPE, None)
    if held is not None:
        held.failed = True


def pytest_bdd_step_func_lookup_error(request: Any, feature: Any, scenario: Any, step: Any, exception: Any) -> None:
    held = request.node.stash.get(_TAPE, None)
    if held is not None:
        held.failed = True


def pytest_bdd_after_scenario(request: pytest.FixtureRequest, feature: Any, scenario: Any) -> None:
    __tracebackhide__ = True
    held = request.node.stash.get(_TAPE, None)
    if held is None:
        return
    tape = held
    del request.node.stash[_TAPE]
    problems = tape.end()
    if problems and tape.failed:  # the step's own failure says more; these only add to it
        import warnings  # noqa: PLC0415
        warnings.warn("\n".join(problems), stacklevel=1)
    elif problems:
        raise AssertionError("\n".join(problems))
