"""Record and replay for a suite's calls to outside services (GRAMMAR.md,
"Record and replay").

One cassette per scenario, in integrations' format (`integrations.cassette/1`):
each scenario runs on `use(Cassette(...))` in replay, or on
`use(Recorder(Network(), ...))` in record mode, saved when it passes. Programs a
scenario runs learn their cassette from `INTEGRATIONS_MODE` and
`INTEGRATIONS_CASSETTE`, and say at exit which recorded calls they used, so an
unused call fails the scenario wherever it was recorded.

integrations is optional: everything here is inert unless
`integrations.transports` imports and the repository turns cassettes on
(`"pubtest": {"cassettes": ...}` in pubrules.json, or `PUBTEST_CASSETTES=1`).
pubtest never depends on integrations, whose own suite runs on pubtest.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .core import repository

__all__ = ["Scenario", "Settings", "Tape", "path_for", "settings", "slug"]

RECORD = "PUBTEST_RECORD"          # 1: record; anything else: replay
SWITCH = "PUBTEST_CASSETTES"       # 1 turns the harness on, 0 off, whatever pubrules.json says
ONLY = "PUBTEST_ONLY"              # a JSON list of scenarios: the others are not run
PLAN = "PUBTEST_PLAN"              # a file: each scenario writes whether its cassette is stale
REPORT = "INTEGRATIONS_CASSETTE_REPORT"  # a file: each program writes the calls it used
RUN = "PUBTEST_RUN"
MODE = "INTEGRATIONS_MODE"
CASSETTE = "INTEGRATIONS_CASSETTE"
CASSETTES = "INTEGRATIONS_CASSETTES"
CHILD = Path(__file__).parent / "_child"
NO_DATA_REPO = "no data repo: `pubtest record --all` creates it"
OFF = ('the integration steps need the record/replay harness: install integrations and set '
       '"pubtest": {"cassettes": ...} in pubrules.json (GRAMMAR.md, "Record and replay")')

# The transport record mode records through: the network. A suite's own tests
# of recording put a stand-in here; nothing else should.
network: Callable[[], Any] | None = None


def transports() -> Any:
    """integrations.transports, or None when integrations is not installed."""
    try:
        return importlib.import_module("integrations.transports")
    except ImportError:
        return None


def slug(title: str) -> str:
    """A scenario's title as a file name: lower-cased, each run of anything but
    a-z and 0-9 one "-", none at either end."""
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "scenario"


@dataclass(frozen=True)
class Scenario:
    """A scenario as a cassette names it: its feature file's name, its title (an
    outline's, its <placeholders> as written) and, for an outline, its Examples
    row, from 1."""

    feature: str
    title: str
    row: int | None = None

    @property
    def stem(self) -> str:
        return self.feature.removesuffix(".feature")

    @property
    def id(self) -> str:
        return f"{self.feature}: {self.title}" + (f" #{self.row}" if self.row else "")

    @property
    def relative(self) -> str:
        if self.row:
            return f"{self.stem}/{slug(self.title)}/{self.row}.json"
        return f"{self.stem}/{slug(self.title)}.json"

    def named_by(self, selector: str) -> bool:
        """Whether `selector` names this scenario: its id, its id without the row,
        "stem: title", the title alone, or its cassette's path without .json."""
        selector = selector.strip()
        names = {self.id, f"{self.feature}: {self.title}", f"{self.stem}: {self.title}", self.title,
                 self.relative.removesuffix(".json")}
        if self.row:
            names.add(f"{self.stem}: {self.title} #{self.row}")
        return selector in names


def parse(selector: str, feature: str | None = None) -> Scenario:
    """A scenario from what a person writes: "FILE: TITLE[ #ROW]", or a TITLE of
    `feature`'s."""
    text = selector.strip()
    row = None
    m = re.fullmatch(r"(.*) #(\d+)", text)
    if m:
        text, row = m.group(1), int(m.group(2))
    head, sep, title = text.partition(": ")
    if sep and head.endswith(".feature"):
        return Scenario(head, title, row)
    if feature is None:
        raise ValueError(f'"{selector}" names no feature: write it "FILE.feature: TITLE"')
    return Scenario(feature, text, row)


def _truthy(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    return value.lower() not in ("0", "false", "no", "off")


def _declared(root: Path) -> Any:
    try:
        data = json.loads((root / "pubrules.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    block = data.get("pubtest") if isinstance(data, dict) else None
    return block.get("cassettes") if isinstance(block, dict) else None


@dataclass
class Settings:
    """The session's: whether the harness is on, its mode, and where cassettes are."""

    active: bool
    mode: str
    root: Path
    cassettes: Path | None
    data_repo: Path | None
    # The cassettes directory is pubrules.json's "DIR", in the repository itself.
    named: bool = False

    @property
    def recording(self) -> bool:
        return self.mode == "record"


def settings(root: Path | None = None, env: dict[str, str] | None = None) -> Settings:
    """The harness's settings for the repository at `root`.

    On when integrations.transports imports and either PUBTEST_CASSETTES is 1 or
    pubrules.json has `"pubtest": {"cassettes": true}` (the data repository's
    directory) or `{"cassettes": "DIR"}` (a directory of the repository's own);
    PUBTEST_CASSETTES=0 turns it off. The cassettes directory is
    INTEGRATIONS_CASSETTES, else DIR, else ../<repo>-data/integrations/cassettes."""
    env = os.environ if env is None else env
    root = (root or repository()).resolve()
    declared = _declared(root)
    switch = _truthy(env.get(SWITCH))
    wanted = switch if switch is not None else bool(declared)
    active = bool(wanted) and transports() is not None
    data_repo = None
    named = False
    if env.get(CASSETTES):
        cassettes = Path(env[CASSETTES]).absolute()
    elif isinstance(declared, str):
        cassettes = (root / declared).absolute()
        named = True
    else:
        data_repo = root.parent / f"{root.name}-data"
        cassettes = data_repo / "integrations" / "cassettes"
    return Settings(active, "record" if _truthy(env.get(RECORD)) else "replay", root, cassettes, data_repo,
                    named)


def stand_in_only(found: Settings, real_network: bool) -> str | None:
    """The warning a recording gives when it records the real network into
    pubrules.json's "DIR": that form is for a suite whose record transport is a
    stand-in (pubtest's own), since the repository is no place for what real
    services answered."""
    if not (found.active and found.recording and found.named and real_network):
        return None
    return (f'pubtest record: warning: {found.cassettes} is pubrules.json\'s "cassettes": "DIR", which is only '
            "for a suite whose record transport is a stand-in; this one records the real network, whose answers "
            'belong in the private data repository ("pubtest": {"cassettes": true})')


def start_session(found: Settings) -> None:
    """At the session's start: refuse a replay with no cassettes at all, make the
    directory a recording needs, and set the variables every program inherits.
    Raises `LookupError` saying what is missing."""
    if not found.active:
        return
    if not found.cassettes.is_dir():
        if found.recording and (found.data_repo is None or found.data_repo.is_dir()):
            found.cassettes.mkdir(parents=True, exist_ok=True)
        else:
            raise LookupError(f"{NO_DATA_REPO} (there is no {found.cassettes})")
    os.environ.setdefault(RUN, uuid.uuid4().hex)
    os.environ[MODE] = found.mode
    os.environ[CASSETTES] = str(found.cassettes.resolve())


def only() -> list[str] | None:
    raw = os.environ.get(ONLY)
    return json.loads(raw) if raw else None


def selected(scenario: Scenario) -> bool:
    chosen = only()
    return chosen is None or any(scenario.named_by(s) for s in chosen)


def path_for(scenario: Scenario, found: Settings | None = None) -> Path:
    """The cassette of `scenario`: <feature stem>/<title slug>.json, or
    <feature stem>/<title slug>/<row>.json for an Examples row, in the cassettes
    directory."""
    found = found or settings()
    if found.cassettes is None:
        raise LookupError(NO_DATA_REPO)
    return found.cassettes / scenario.relative


def matches_name(name: str, plugin: str | None) -> bool:
    """NAME is a plugin's id (`github.edit-pr`) or what every id it stands for
    starts with, before a dot (`github` is every github.* plugin)."""
    plugin = plugin or ""
    return plugin == name or plugin.startswith(name + ".")


def text_hash(steps: list[tuple[str, str | None, list[list[str]] | None]]) -> str:
    """The scenario's steps as it runs them: each one's text, docstring and table."""
    lines = []
    for text, docstring, table in steps:
        lines.append(text)
        if docstring is not None:
            lines.append('"""\n' + docstring + '\n"""')
        for row in table or []:
            lines.append("| " + " | ".join(row) + " |")
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def _git(root: Path, *args: str) -> str:
    try:
        done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False, timeout=30)
    except OSError:
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def consumer(root: Path) -> str:
    """<repo>@<commit>: the repository the recording was made from."""
    origin = _git(root, "remote", "get-url", "origin")
    name = re.sub(r"\.git$", "", origin.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]) if origin else root.name
    return f"{name}@{_git(root, 'rev-parse', 'HEAD') or 'uncommitted'}"


def integrations_version() -> str:
    try:
        return importlib.import_module("integrations").__version__
    except (ImportError, AttributeError):
        return "unknown"


class Clock:
    """The scenario's clock, sleep and jitter for a Caller. In replay nothing waits:
    a sleep moves the clock on, as `Faulty`'s slow answers do, and the jitter is
    half its range. In record mode a sleep waits."""

    def __init__(self, fake: bool) -> None:
        self.fake, self.offset, self.slept, self.base = fake, 0.0, 0.0, time.monotonic()

    def now(self) -> float:
        return (self.base if self.fake else time.monotonic()) + self.offset

    def sleep(self, seconds: float) -> None:
        self.slept += seconds
        if self.fake:
            self.offset += seconds
        else:
            time.sleep(seconds)

    def advance(self, seconds: float) -> None:
        self.offset += seconds

    def random(self) -> float:
        return 0.5 if self.fake else random.random()


class _Hold:
    """A transport that hands each call to `fn`."""

    def __init__(self, fn: Callable[[Any, float], Any]) -> None:
        self.send = fn


class Tape:
    """One scenario's calls: its cassette, the faults put on it, the clock, the
    requests made, and the names its test customers gave."""

    def __init__(self, found: Settings, scenario: Scenario, tags: set[str], steps_text: str) -> None:
        self.t = transports()
        self.settings, self.scenario, self.text = found, scenario, steps_text
        self.path = path_for(scenario, found)
        self.borrowed: Path | None = None
        for tag in tags:
            if tag.startswith("cassette:"):
                self.borrow(tag.removeprefix("cassette:").strip('"'))
        self.clock = Clock(fake=not found.recording or self.borrowed is not None)
        self.requests: list[tuple[str | None, str | None]] = []
        self.errors: list[str] = []
        self.sources: list[str] = []
        self.names: dict[str, dict[str, str]] = {}
        self.customers: dict[str, Any] = {}
        self.cassette = None
        self.recorder = None
        self.failed = False
        work = Path(tempfile.mkdtemp(prefix="pubtest-cassette-"))
        self.work, self.report = work, work / "report.jsonl"
        self.faulty = self.t.Faulty(_Hold(self._inner), [], advance=self.clock.advance)
        self._saved_env: dict[str, str | None] = {}
        self._defaults: dict[str, Any] | None = None
        self._use = None
        if not found.recording or self.borrowed is not None:
            self._replayed_names()

    # --- what the steps change -------------------------------------------------

    def borrow(self, selector: str) -> None:
        """Replay another scenario's cassette: a fault scenario's, over a recording
        of the scenario it breaks. `selector` names the scenario ("FILE: TITLE", or
        a TITLE of this feature's), or, as a tag must for want of spaces, its
        cassette's path without .json."""
        if "/" in selector and ": " not in selector:
            self.borrowed = self.settings.cassettes / (selector.removesuffix(".json") + ".json")
        else:
            self.borrowed = path_for(parse(selector, self.scenario.feature), self.settings)
        self.cassette = None
        if hasattr(self, "clock"):
            self.clock.fake = True
            self._replayed_names()

    def fault(self, name: str, effect: str, nth: str = "*", where: str = "", body: str | None = None) -> None:
        """A fault on the calls to NAME (a plugin, or a prefix of plugins), matching
        "METHOD PATH" when `where` gives one."""
        fault = _prefixed(self.t)({"match": f"* {where}".strip(), "nth": nth, "effect": effect,
                                   **({"body": body} if body is not None else {})}, name)
        self.faulty.rules.append(fault)

    def names_of(self, customer: str) -> dict[str, str]:
        """The names a test customer gave: made by its setup when recording, read
        back from the cassette in replay."""
        if customer not in self.names and self.settings.recording and self.borrowed is None:
            found = self.customers.get(customer)
            if found is None:
                raise LookupError(f"no test customer {customer}: a package registers it in pubtest.customers")
            self.names[customer] = dict(getattr(found, "setup", lambda ctx: {})(self) or {})
        return self.names.setdefault(customer, {})

    # --- the transport ------------------------------------------------------------

    def send(self, request: Any, timeout: float) -> Any:
        self.requests.append((request.plugin or None, request.operation or None))
        return self.faulty.send(request, timeout)

    def _inner(self, request: Any, timeout: float) -> Any:
        if self.settings.recording and self.borrowed is None:
            if self.recorder is None:
                inner = network() if network is not None else self.t.Network()
                self.recorder = self.t.Recorder(inner, None, scenario=self.scenario.id,
                                                consumer=consumer(self.settings.root), clock=self.clock.now)
            return self.recorder.send(request, timeout)
        return self._loaded().send(request, timeout)

    def _loaded(self) -> Any:
        if self.cassette is None:
            source = self.borrowed or self.path
            if not source.is_file():
                whose = self.scenario.id if self.borrowed is None else source.relative_to(self.settings.cassettes)
                message = f'no cassette for {whose}: record it (`pubtest record "{self.scenario.id}"`)'
                self.errors.append(message)
                raise self.t.NoSnapshot(message)
            cassette = self.t.Cassette(source, mode="replay")
            answer = cassette.send

            def send(request: Any, timeout: float) -> Any:
                try:
                    return answer(request, timeout)
                except self.t.NoSnapshot as e:  # kept, so code that swallows it still fails the scenario
                    self.errors.append(str(e))
                    raise
            cassette.send = send
            self.cassette = cassette
        return self.cassette

    def _replayed_names(self) -> None:
        source = self.borrowed or self.path
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        names = ((data.get("current") or {}).get("recorded") or {}).get("pubtest", {}).get("names") or {}
        self.names = {k: dict(v) for k, v in names.items()}

    # --- the scenario's start and end ----------------------------------------------

    def begin(self) -> None:
        self._use = self.t.use(_Hold(self.send))
        self._use.__enter__()
        self._patch_caller()
        child_cassette = self.borrowed or self.path
        env = {CASSETTE: str(child_cassette), REPORT: str(self.report)}
        if self.settings.recording and self.borrowed is None:
            # A program records into a file of its own, which the scenario takes
            # as its recording when it makes no calls itself.
            env = {CASSETTE: str(self.work / "child.json"), CASSETTES: str(self.work.resolve()),
                   REPORT: str(self.report)}
        env["PYTHONPATH"] = os.pathsep.join(p for p in (str(CHILD), os.environ.get("PYTHONPATH")) if p)
        hook = f"--import={(CHILD / 'report.mjs').as_uri()}"
        env["NODE_OPTIONS"] = " ".join(p for p in (os.environ.get("NODE_OPTIONS"), hook) if p)
        for key, value in env.items():
            self._saved_env[key] = os.environ.get(key)
            os.environ[key] = value

    def _patch_caller(self) -> None:
        calls = sys.modules.get("integrations.calls") or importlib.import_module("integrations.calls")
        defaults = calls.Caller.__init__.__kwdefaults__
        self._defaults = dict(defaults)
        defaults.update(clock=self.clock.now, sleep=self.clock.sleep, random=self.clock.random)

    def step(self, fn: Callable) -> None:
        try:
            self.sources.append(inspect.getsource(fn))
        except (OSError, TypeError):
            self.sources.append(getattr(fn, "__qualname__", repr(fn)))

    @property
    def steps_hash(self) -> str:
        return hashlib.sha256("\n".join(self.sources).encode()).hexdigest()

    def children(self) -> list[dict]:
        if not self.report.is_file():
            return []
        return [json.loads(line) for line in self.report.read_text(encoding="utf-8").splitlines() if line.strip()]

    def end(self, close: Callable[[], Any] | None = None) -> list[str]:
        """Close the scenario: stop answering from its tape, check or save its
        cassette, then run `close` (the scenario's own cleanups) and its
        customers' cleanups while its environment is still set, and only then
        undo what begin() did to the environment. The cleanups call through the
        record transport itself, so nothing records or faults them. Returns what
        fails it: every problem, a failed cleanup's among them."""
        problems: list[str] = []
        own = self.settings.recording and self.borrowed is None
        try:
            if self._use is not None:
                self._use.__exit__(None, None, None)
                self._use = None
            if self._defaults is not None:
                calls = sys.modules["integrations.calls"]
                calls.Caller.__init__.__kwdefaults__.clear()
                calls.Caller.__init__.__kwdefaults__.update(self._defaults)
                self._defaults = None
            if own:
                if not self.failed:
                    problems += self._save()
            else:
                problems += self._check()
            if os.environ.get(PLAN):
                self._plan(problems)
        finally:
            direct = self.t.use(network() if network is not None else self.t.Network()) if own else None
            if direct is not None:
                direct.__enter__()
            try:
                if close is not None:
                    try:
                        close()
                    except Exception as e:  # noqa: BLE001 - the customers' cleanups still run
                        problems.append("a cleanup failed: " + "".join(traceback.format_exception(e)).rstrip())
                if own:
                    for name, customer in self.customers.items():
                        if name in self.names and hasattr(customer, "cleanup"):
                            try:
                                customer.cleanup(self, self.names[name])
                            except Exception as e:  # noqa: BLE001 - every cleanup runs, and says so
                                problems.append(f"the test customer {name}'s cleanup failed: {e}")
            finally:
                if direct is not None:
                    direct.__exit__(None, None, None)
                for key, value in self._saved_env.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
                _rmtree(self.work)
        return problems

    def _check(self) -> list[str]:
        problems = list(dict.fromkeys(self.errors)) if not self.failed else []
        children = self.children()
        missed = sum(max(0, c.get("sent", 0) - c.get("answered", 0)) for c in children)
        if missed and not self.failed:
            problems.append(f"{missed} call{'s' * (missed != 1)} a program made had no recording in "
                            f"{self.scenario.id}: record it (`pubtest record \"{self.scenario.id}\"`)")
        if self.borrowed is not None or self.failed or not self.path.is_file():
            return problems
        cassette = self.cassette or self.t.Cassette(self.path, mode="replay")
        used = {i for i, call in enumerate(cassette.calls) if call.used}
        # A program names the cassette it replayed as begin() gave it, in
        # INTEGRATIONS_CASSETTE: compared as text, a path read from its report
        # is never looked up on disk.
        mine = str(self.path)
        for child in children:
            if child.get("cassette") == mine:
                used.update(child.get("used", []))
        left = [i for i in range(len(cassette.calls)) if i not in used]
        if left:
            lines = [f"{len(left)} recorded call{'s' * (len(left) != 1)} in {self.scenario.id} never made:"]
            for i in left:
                call = cassette.calls[i]
                lines.append(f"  {call.plugin or '*'} {call.operation or '*'} {call.request['method'].upper()} "
                             f"{call.request['url']}")
            lines.append(f'record it: pubtest record "{self.scenario.id}"')
            problems.append("\n".join(lines))
        return problems

    def _stamp(self, current: dict) -> dict:
        recorded = current.setdefault("recorded", {})
        recorded["integrations"] = integrations_version()
        recorded["consumer"] = recorded.get("consumer") or consumer(self.settings.root)
        recorded["pubtest"] = {"scenario": self.text, "steps": self.steps_hash, "names": self.names}
        return current

    def _save(self) -> list[str]:
        own = self.recorder.calls if self.recorder is not None else []
        child_file = self.work / "child.json"
        child = json.loads(child_file.read_text(encoding="utf-8")) if child_file.is_file() else None
        if own and child:
            return [f"{self.scenario.id} made calls itself and through a program it ran: a cassette holds one "
                    "process's calls, so record them in separate scenarios"]
        try:
            current = self.recorder.recording() if own else (child or {}).get("current")
        except self.t.SecretInRecording as e:
            return [str(e)]
        if not current or not current.get("calls"):
            if self.path.is_file():
                self.path.unlink()  # it makes no calls now: its old cassette goes
            return []
        old: dict = {}
        if self.path.is_file():
            old = json.loads(self.path.read_text(encoding="utf-8"))
        baseline = None
        if old.get("format") == self.t.FORMAT:
            baseline = old.get("baseline") if old.get("baseline") is not None else old.get("current")
        self.t.write_cassette(self.path, {"format": self.t.FORMAT, "scenario": self.scenario.id,
                                          "current": self._stamp(current), "baseline": baseline},
                              self.settings.cassettes)
        return []

    def _plan(self, problems: list[str]) -> None:
        """Whether this scenario's cassette needs recording again, for
        `pubtest record --changed`."""
        reason = None
        if self.borrowed is None:
            if any(e.startswith("no cassette for") for e in self.errors):
                reason = "it has no cassette"
            elif problems:
                reason = "it no longer fits its cassette"
            elif self.path.is_file():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                recorded = (data.get("current") or {}).get("recorded") or {}
                stamp = recorded.get("pubtest") or {}
                if stamp.get("scenario") != self.text:
                    reason = "its text changed"
                elif stamp.get("steps") != self.steps_hash:
                    reason = "its steps' code changed"
                elif recorded.get("integrations") != integrations_version():
                    reason = f"integrations is {integrations_version()}, not {recorded.get('integrations')}"
        with open(os.environ[PLAN], "a", encoding="utf-8") as out:
            out.write(json.dumps({"scenario": self.scenario.id, "changed": reason}) + "\n")


def _prefixed(t: Any) -> type:
    class Prefixed(t.Fault):
        """A Fault on NAME's calls: a plugin, or every plugin under a prefix."""

        def __init__(self, rule: dict, name: str) -> None:
            super().__init__(rule)
            self.name = name

        def matches(self, request: Any) -> bool:
            return matches_name(self.name, request.plugin) and super().matches(request)
    return Prefixed


def _rmtree(path: Path) -> None:
    import shutil  # noqa: PLC0415
    shutil.rmtree(path, ignore_errors=True)
