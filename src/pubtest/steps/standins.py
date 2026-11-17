"""Stand-in programs: scripts first on PATH in place of real ones, each run
recorded, so a suite tests what drives kubectl, ssh or git without them."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from pytest_bdd import given, parsers, then

# What a stand-in-only PATH still holds: the shell's basic tools.
BASIC = ("sh", "bash", "env", "cat", "echo", "printf", "mkdir", "rm", "cp", "mv", "chmod", "ls", "sed",
         "grep", "head", "tail", "tr", "cut", "sort", "uniq", "wc", "dirname", "basename", "mktemp", "date",
         "sleep", "true", "false", "test", "touch", "readlink", "realpath", "id", "uname")

# A stand-in that answers in turn: the first answer whose args match, of
# those not yet given, else the last that matches.
TURNS = '''#!{python}
import json, re, sys
with open({log!r}, "a", encoding="utf-8") as log:
    log.write(json.dumps({{"name": {name!r}, "args": sys.argv[1:]}}) + "\\n")
with open({answers!r}, encoding="utf-8") as f:
    answers = json.load(f)
args = " ".join(sys.argv[1:])
matching = [a for a in answers if re.fullmatch(".*".join(map(re.escape, a["args"].split("*"))), args, re.S)]
fresh = [a for a in matching if not a.get("given")]
none = {{"exit": 127, "stdout": "", "stderr": {name!r} + ": no answer for " + args + "\\n"}}
answer = fresh[0] if fresh else (matching[-1] if matching else none)
answer["given"] = True
with open({answers!r}, "w", encoding="utf-8") as f:
    json.dump(answers, f)
sys.stdout.write(answer.get("stdout", ""))
sys.stderr.write(answer.get("stderr", ""))
sys.exit(int(answer.get("exit", 0)))
'''

STANDIN = '''#!{python}
import json, sys
with open({log!r}, "a", encoding="utf-8") as log:
    log.write(json.dumps({{"name": {name!r}, "args": sys.argv[1:]}}) + "\\n")
sys.stdout.write({out!r})
sys.stderr.write({err!r})
sys.exit({code})
'''


class Standins:
    """A directory of stand-ins, its log of runs, and the PATH it makes."""

    def __init__(self, root: Path) -> None:
        self.bin = root / "standins"
        self.bin.mkdir(parents=True)
        self.log = root / "standins.log"
        self.log.touch()
        self.only = False
        self.basic = root / "basic"

    def add(self, name: str, out: str = "", err: str = "", code: int = 0) -> None:
        path = self.bin / name
        path.write_text(STANDIN.format(python=sys.executable, log=str(self.log), name=name, out=out, err=err,
                                       code=code), encoding="utf-8")
        path.chmod(0o755)

    def add_turns(self, name: str, answers: list[dict]) -> None:
        store = self.bin.parent / f"{name}.answers.json"
        store.write_text(json.dumps(answers), encoding="utf-8")
        path = self.bin / name
        path.write_text(TURNS.format(python=sys.executable, log=str(self.log), name=name, answers=str(store)),
                        encoding="utf-8")
        path.chmod(0o755)

    def remove(self, name: str) -> None:
        (self.bin / name).unlink(missing_ok=True)

    def path(self) -> str:
        if not self.only:
            return f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}"
        self.basic.mkdir(exist_ok=True)
        for tool in BASIC:
            found = shutil.which(tool)
            if found and not (self.basic / tool).exists() and not (self.bin / tool).exists():
                (self.basic / tool).symlink_to(found)
        return f"{self.bin}{os.pathsep}{self.basic}"

    def runs(self, name: str | None = None) -> list[list[str]]:
        entries = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines() if line]
        return [e["args"] for e in entries if name is None or e["name"] == name]


def standins(pubtest_ctx, tmp_path) -> Standins:
    if getattr(pubtest_ctx, "standins", None) is None:
        pubtest_ctx.standins = Standins(tmp_path / "pubtest")
        previous = os.environ.get("PATH", "")
        os.environ["PATH"] = pubtest_ctx.standins.path()

        @pubtest_ctx.cleanup
        def restore():
            os.environ["PATH"] = previous
    return pubtest_ctx.standins


def _refresh(pubtest_ctx) -> None:
    os.environ["PATH"] = pubtest_ctx.standins.path()


@given(parsers.re(r'a stand-in "(?P<name>[^"]+)"'))
def standin(pubtest_ctx, tmp_path, name):
    standins(pubtest_ctx, tmp_path).add(name)
    _refresh(pubtest_ctx)


@given(parsers.parse('a stand-in "{name}" that prints "{text}"'))
def standin_prints(pubtest_ctx, tmp_path, name, text):
    standins(pubtest_ctx, tmp_path).add(name, out=text + "\n")
    _refresh(pubtest_ctx)


@given(parsers.parse('a stand-in "{name}" that prints:'))
def standin_prints_text(pubtest_ctx, tmp_path, name, docstring):
    standins(pubtest_ctx, tmp_path).add(name, out=docstring + "\n")
    _refresh(pubtest_ctx)


@given(parsers.parse('a stand-in "{name}" that fails, saying "{text}"'))
def standin_fails(pubtest_ctx, tmp_path, name, text):
    standins(pubtest_ctx, tmp_path).add(name, err=text + "\n", code=1)
    _refresh(pubtest_ctx)


@given(parsers.parse('a stand-in "{name}" that answers in turn:'))
def standin_turns(pubtest_ctx, tmp_path, name, datatable):
    """A row per answer: args (a pattern, * for any), and optionally exit,
    stdout and stderr. A run takes the first matching answer not yet given,
    or the last that matches once all are given."""
    keys, rows = datatable[0], datatable[1:]
    answers = []
    for row in rows:
        answer = dict(zip(keys, row, strict=True))
        for stream in ("stdout", "stderr"):
            if answer.get(stream):
                answer[stream] = answer[stream].replace("\\n", "\n") + "\n"
        answers.append(answer)
    standins(pubtest_ctx, tmp_path).add_turns(name, answers)
    _refresh(pubtest_ctx)


@given("only stand-ins are installed")
def only_standins(pubtest_ctx, tmp_path):
    standins(pubtest_ctx, tmp_path).only = True
    _refresh(pubtest_ctx)


@given(parsers.parse('"{name}" is not installed'))
def not_installed(pubtest_ctx, tmp_path, name):
    found = standins(pubtest_ctx, tmp_path)
    found.remove(name)
    found.only = True
    _refresh(pubtest_ctx)


@then(parsers.parse('"{name}" was run with "{args}"'))
def run_with(pubtest_ctx, name, args):
    import shlex  # noqa: PLC0415
    runs = pubtest_ctx.standins.runs(name)
    assert shlex.split(args) in runs, f"{name} ran with {runs}"


@then(parsers.parse('"{name}" was run {count:d} times'))
def run_times(pubtest_ctx, name, count):
    assert len(pubtest_ctx.standins.runs(name)) == count, f"{name} ran {len(pubtest_ctx.standins.runs(name))} times"


@then(parsers.parse('"{name}" was not run'))
def not_run(pubtest_ctx, name):
    runs = pubtest_ctx.standins.runs(name) if getattr(pubtest_ctx, "standins", None) else []
    assert not runs, f"{name} ran with {runs}"


@then("nothing was run")
def nothing_run(pubtest_ctx):
    runs = pubtest_ctx.standins.runs() if getattr(pubtest_ctx, "standins", None) else []
    assert not runs, f"ran: {runs}"
