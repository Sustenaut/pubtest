"""What every step shares: a scenario's context, a program's run, and how a
step's quoted value is compared."""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

__all__ = ["Completed", "Context", "Refused", "Result", "bin_var", "dig", "same", "value"]


@dataclass(frozen=True)
class Completed:
    """The observable result of running a program."""

    argv: list[str]
    code: int
    out: bytes
    err: bytes

    @property
    def stdout(self) -> str:
        return self.out.decode("utf-8", "replace")

    @property
    def stderr(self) -> str:
        return self.err.decode("utf-8", "replace")

    @property
    def lines(self) -> list[str]:
        return self.stdout.splitlines()

    def describe(self) -> str:
        return (f"$ {' '.join(self.argv)}\nexit {self.code}\n"
                f"stdout: {self.stdout!r}\nstderr: {self.stderr!r}")


@dataclass
class Refused:
    """What an attempted action raised."""

    error: BaseException

    @property
    def message(self) -> str:
        if isinstance(self.error, SystemExit):
            code = self.error.code
            return "" if code is None or isinstance(code, int) else str(code)
        return str(self.error)


@dataclass
class Result:
    """What a scenario's action came to, whichever kind of When it was: the
    value it returned or the refusal it raised, and its exit code and what it
    printed. `I run` fills the code and output; `attempt` fills the value or
    the refusal, and the output too, with code 0 for a return, 1 for a raise
    and the SystemExit code for an exit."""

    value: Any = None
    refused: Refused | None = None
    code: int = 0
    stdout: str = ""
    stderr: str = ""
    argv: list[str] = field(default_factory=list)

    @property
    def returncode(self) -> int:
        return self.code

    def describe(self) -> str:
        head = f"$ {' '.join(self.argv)}\n" if self.argv else ""
        refused = f"refused: {self.refused.message!r}\n" if self.refused else ""
        return f"{head}exit {self.code}\n{refused}stdout: {self.stdout!r}\nstderr: {self.stderr!r}"


@dataclass
class Context(SimpleNamespace):
    """A scenario's state: what its action came to, the scratch directory,
    the secrets, and the cleanups that run when it ends, in reverse, passed
    or failed."""

    outcome: Result | None = None
    refusal_read: bool = False
    directory: Path | None = None
    secrets: list[str] = field(default_factory=list)
    written: dict[str, bytes] | None = None
    _cleanups: list[Callable[[], Any]] = field(default_factory=list)

    @property
    def result(self) -> Any:
        return self.outcome.value if self.outcome else None

    @property
    def refused(self) -> Refused | None:
        return self.outcome.refused if self.outcome else None

    def cleanup(self, fn: Callable[[], Any]) -> Callable[[], Any]:
        """Run `fn` when the scenario ends; usable as a decorator."""
        self._cleanups.append(fn)
        return fn

    def acting(self) -> None:
        """Before an action: the scratch directory as it was before the first one."""
        if self.directory is not None and self.written is None:
            self.written = files_in(self.directory)

    def attempt(self, action: Callable[[], Any]) -> Any:
        """Do the scenario's action: keep what it returns, or what it raises,
        and what it printed. An awaitable it returns is awaited."""
        import asyncio  # noqa: PLC0415
        import contextlib  # noqa: PLC0415
        import inspect  # noqa: PLC0415
        import io  # noqa: PLC0415
        self.acting()
        out, err = io.StringIO(), io.StringIO()
        outcome = Result()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                returned = action()
                if inspect.isawaitable(returned):
                    returned = asyncio.run(_awaited(returned))
            outcome.value = returned
        except SystemExit as exit_:
            outcome.refused = Refused(exit_)
            outcome.code = exit_.code if isinstance(exit_.code, int) else (0 if exit_.code is None else 1)
            if outcome.code == 0:
                outcome.refused = None
        except Exception as error:  # noqa: BLE001 - the refusal is the point
            outcome.refused, outcome.code = Refused(error), 1
        outcome.stdout, outcome.stderr = out.getvalue(), err.getvalue()
        self.outcome, self.refusal_read = outcome, False
        return outcome.value

    def ran(self, outcome: "Result") -> "Result":
        """Keep a program's run as what the action came to."""
        self.outcome, self.refusal_read = outcome, False
        return outcome

    def unread_refusal(self) -> BaseException | None:
        """A refusal no Then read: the scenario fails with it."""
        if self.refused is not None and not self.refusal_read:
            return self.refused.error
        return None

    def close(self) -> None:
        errors: list[BaseException] = []
        while self._cleanups:
            fn = self._cleanups.pop()
            try:
                fn()
            except Exception as e:  # noqa: BLE001 - every cleanup must run
                errors.append(e)
        if errors:
            raise errors[0]


async def _awaited(awaitable):
    return await awaitable


def files_in(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def bin_var(name: str) -> str:
    """The variable naming the directory that holds `name`: pub -> PUB_BIN_DIR."""
    return re.sub(r"[^A-Za-z0-9]", "_", name).upper() + "_BIN_DIR"


def program(name: str, var: str | None = None) -> Path:
    """The program under test `name`, from `<NAME>_BIN_DIR`, never from PATH."""
    var = var or bin_var(name)
    raw = os.environ.get(var)
    if not raw:
        raise LookupError(f"{var} is not set: it must name the directory holding {name}")
    path = Path(raw) / (name + (".exe" if sys.platform == "win32" else ""))
    if not path.exists():
        raise LookupError(f"{var}={raw} has no {name}")
    return path


def value(text: str) -> Any:
    """A step's quoted value: JSON when it reads as JSON, text otherwise."""
    try:
        return json.loads(text)
    except ValueError:
        return text


def same(actual: Any, wanted: str) -> bool:
    """Whether `actual` is the step's value V. When the result is text, V is
    compared as text. Otherwise V is read as JSON and compared as a value; a
    V that does not read as JSON is compared with the result's text."""
    if isinstance(actual, (bytes, bytearray)):
        actual = actual.decode("utf-8", "replace")
    if isinstance(actual, str):
        return actual == wanted
    try:
        want = json.loads(wanted)
    except ValueError:
        return str(actual) == wanted
    if isinstance(actual, bool) != isinstance(want, bool):
        return False  # true is not 1, and 0 is not false
    return actual == want


def dig(data: Any, key: str) -> Any:
    """The value at a dotted key: `a.b.0` is data["a"]["b"][0]."""
    for part in key.split("."):
        if isinstance(data, list):
            data = data[int(part)]
        elif isinstance(data, dict):
            data = data[part]
        else:
            data = getattr(data, part)
    return data


def includes(container: Any, item: str) -> bool:
    """Text contains it, a list holds it, a map has it as a key; the item is
    compared as text with text, and read as JSON otherwise."""
    if isinstance(container, (bytes, bytearray)):
        container = container.decode("utf-8", "replace")
    if isinstance(container, str):
        return item in container
    want = value(item)
    if isinstance(container, dict):
        return want in container or item in container
    return want in container or item in [str(x) for x in container]


def show(data: Any) -> str:
    try:
        return json.dumps(data, indent=2, default=str)
    except TypeError:
        return repr(data)
