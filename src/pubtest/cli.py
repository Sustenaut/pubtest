"""`pubtest record`: record the cassettes of a suite's scenarios (GRAMMAR.md,
"Record and replay").

    pubtest record --all                 every scenario
    pubtest record --changed             the scenarios whose cassette is out of date
    pubtest record "FILE: TITLE" ...     these scenarios
    pubtest record --rename OLD NEW      move a scenario's cassette to its new name

It runs the repository's suite with PUBTEST_RECORD=1: pytest-bdd for a Python
repository, cucumber-js for a Node one (pubrules.json's ci.language, else this
program's own). The same command is in the npm package.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from . import cassettes
from .core import repository

# What a harness sets for the programs it runs, which a suite run from inside
# one (pubtest's own) must not inherit.
HARNESS = (cassettes.RUN, cassettes.MODE, cassettes.CASSETTE, cassettes.CASSETTES, cassettes.REPORT,
           cassettes.ONLY, cassettes.PLAN, cassettes.RECORD)

README = """# {name}

The recorded answers {repo}'s tests replay: one cassette per scenario under
`integrations/cassettes/`, in integrations' `integrations.cassette/1` format,
written by `pubtest record` in {repo}. Private: a recording holds no secret,
but it does hold what the services answered.
"""


def _fail(message: str, code: int = 2) -> int:
    print(f"pubtest record: {message}", file=sys.stderr)
    return code


def _env() -> dict[str, str]:
    env = dict(os.environ)
    if env.get(cassettes.RUN):
        for key in HARNESS:
            env.pop(key, None)
    env[cassettes.SWITCH] = "1"
    return env


def _language(root: Path, own: str) -> str:
    try:
        language = json.loads((root / "pubrules.json").read_text(encoding="utf-8")).get("ci", {}).get("language")
    except (OSError, ValueError, AttributeError):
        language = None
    if language in ("node", "javascript", "typescript", "js"):
        return "node"
    if language == "python":
        return "python"
    return own


def runner(root: Path, language: str) -> tuple[list[str], Path]:
    """The suite's command, and where it runs."""
    if language == "python":
        here = root / "tests" if (root / "tests" / "pytest.ini").is_file() else root
        python = sys.executable if Path(sys.executable).exists() else "python3"
        return [python, "-m", "pytest", "-q", "-p", "no:cacheprovider"], here
    cucumber = root / "node_modules" / "@cucumber" / "cucumber" / "bin" / "cucumber.js"
    return (["node", str(cucumber)] if cucumber.is_file() else ["npx", "cucumber-js"]), root


def _owner(root: Path) -> str | None:
    origin = cassettes._git(root, "remote", "get-url", "origin")
    if not origin:
        return None
    path = origin.removesuffix(".git").replace(":", "/").split("/")
    return path[-2] if len(path) >= 2 else None


def data_repo(found: cassettes.Settings, create: bool) -> int:
    """Make sure the cassettes directory is there: a directory of the repository's
    own is made; a missing data repository is created with gh only when asked."""
    if found.cassettes.is_dir():
        return 0
    if found.data_repo is None or found.data_repo.is_dir():
        found.cassettes.mkdir(parents=True, exist_ok=True)
        return 0
    owner = _owner(found.root) or "OWNER"
    name = found.data_repo.name
    command = ["gh", "repo", "create", f"{owner}/{name}", "--private", "--clone",
               "--description", f"The recorded answers {found.root.name}'s tests replay"]
    if not create:
        print(f"{cassettes.NO_DATA_REPO.split(':')[0]} at {found.data_repo}. Create it, private and beside "
              f"this repository, with:\n\n  (cd {found.root.parent} && {' '.join(_quoted(command))})\n\n"
              "or run pubtest record again with --create-data-repo, which runs that and commits its README, "
              "pubrules.json and integrations.json.", file=sys.stderr)
        return 1
    done = subprocess.run(command, cwd=found.root.parent, check=False)
    if done.returncode != 0 or not found.data_repo.is_dir():
        return _fail("gh repo create failed", done.returncode or 1)
    repo = found.data_repo
    (repo / "README.md").write_text(README.format(name=name, repo=found.root.name), encoding="utf-8")
    (repo / "pubrules.json").write_text(json.dumps({"kind": "content"}, indent=2) + "\n", encoding="utf-8")
    (repo / "integrations.json").write_text(json.dumps(
        {"uses": [], "exclude": [{"path": "**", "reason": "Recorded answers, not code"}]}, indent=2) + "\n",
        encoding="utf-8")
    found.cassettes.mkdir(parents=True, exist_ok=True)
    (found.cassettes / ".gitkeep").write_text("", encoding="utf-8")
    for args in (["add", "-A"], ["commit", "-q", "-m", "Start the data repository"], ["push", "-q", "-u", "origin",
                                                                                         "HEAD"]):
        if subprocess.run(["git", *args], cwd=repo, check=False).returncode != 0:
            return _fail(f"git {' '.join(args)} failed in {repo}", 1)
    return 0


def _quoted(words: list[str]) -> list[str]:
    import shlex  # noqa: PLC0415
    return [shlex.quote(w) for w in words]


def _find(found: cassettes.Settings, selector: str) -> cassettes.Scenario:
    """The scenario `selector` names among the recorded ones, when it names no
    feature file itself."""
    try:
        return cassettes.parse(selector)
    except ValueError:
        pass
    hits = []
    for path in sorted(found.cassettes.rglob("*.json")):
        try:
            recorded = json.loads(path.read_text(encoding="utf-8")).get("scenario", "")
            scenario = cassettes.parse(recorded)
        except (OSError, ValueError, AttributeError):
            continue
        if scenario.named_by(selector):
            hits.append(scenario)
    if len(hits) != 1:
        raise LookupError(f'"{selector}" names {len(hits)} recorded scenarios: write it "FILE.feature: TITLE"')
    return hits[0]


def rename(found: cassettes.Settings, old: str, new: str) -> int:
    try:
        before = _find(found, old)
        after = cassettes.parse(new, before.feature)
    except (LookupError, ValueError) as e:
        return _fail(str(e))
    source, target = cassettes.path_for(before, found), cassettes.path_for(after, found)
    if not source.is_file():
        return _fail(f"{before.id} has no cassette: there is no {source}")
    if target.exists():
        return _fail(f"{after.id} has a cassette already: {target}")
    root = found.cassettes.resolve()
    if not target.resolve().is_relative_to(root):
        return _fail(f"{target} is outside the cassettes directory {root}")
    data = json.loads(source.read_text(encoding="utf-8"))
    data["scenario"] = after.id
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    source.unlink()
    for directory in (source.parent, source.parent.parent):
        if directory != root and directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
    print(f"{source.relative_to(root)} -> {target.relative_to(root)}")
    return 0


def changed(command: list[str], where: Path) -> list[str] | None:
    """The scenarios whose cassette is out of date: the suite runs in replay and
    each scenario says whether it no longer fits its cassette, has none though it
    makes calls, or its text, step code or integrations differ from its recording."""
    with tempfile.TemporaryDirectory(prefix="pubtest-plan-") as work:
        plan = Path(work) / "plan.jsonl"
        env = _env()
        env[cassettes.PLAN] = str(plan)
        subprocess.run(command, cwd=where, env=env, check=False, stdout=subprocess.DEVNULL)
        if not plan.is_file():
            return None
        entries = [json.loads(line) for line in plan.read_text(encoding="utf-8").splitlines() if line.strip()]
    found = {}
    for entry in entries:
        if entry.get("changed"):
            found[entry["scenario"]] = entry["changed"]
    for scenario, reason in found.items():
        print(f"{scenario}: {reason}", flush=True)
    return list(found)


def record(argv: list[str] | None = None, own: str = "python") -> int:
    parser = argparse.ArgumentParser(prog="pubtest record", description="Record the cassettes of a suite's scenarios.")
    which = parser.add_mutually_exclusive_group()
    which.add_argument("--all", action="store_true", help="every scenario")
    which.add_argument("--changed", action="store_true", help="the scenarios whose cassette is out of date")
    parser.add_argument("--rename", nargs=2, metavar=("OLD", "NEW"), help="move OLD's cassette to NEW")
    parser.add_argument("--create-data-repo", action="store_true", help="create the data repository with gh")
    parser.add_argument("scenarios", nargs="*", metavar="SCENARIO", help='"FILE.feature: TITLE[ #ROW]"')
    args = parser.parse_args(argv)
    root = repository()
    found = cassettes.settings(root, _env())
    if args.rename:
        if args.all or args.changed or args.scenarios:
            return _fail("--rename moves one cassette, and records nothing")
        return rename(found, *args.rename)
    if not (args.all or args.changed or args.scenarios):
        return _fail("say which: --all, --changed, or the scenarios")
    if args.all and args.scenarios or args.changed and args.scenarios:
        return _fail("--all and --changed take no scenarios")
    made = data_repo(found, args.create_data_repo)
    if made:
        return made
    command, where = runner(root, _language(root, own))
    chosen: list[str] | None = None if args.all else list(args.scenarios)
    if args.changed:
        chosen = changed(command, where)
        if chosen is None:
            return _fail("the suite said nothing about its scenarios: is pubtest's harness on in it?", 1)
        if not chosen:
            print("no scenario's cassette is out of date", flush=True)
            return 0
    env = _env()
    env[cassettes.RECORD] = "1"
    if chosen is not None:
        env[cassettes.ONLY] = json.dumps(chosen)
    before = _stamps(found.cassettes)
    done = subprocess.run(command, cwd=where, env=env, check=False)
    after = _stamps(found.cassettes)
    for path in sorted(p for p, stamp in after.items() if before.get(p) != stamp):
        print(f"recorded {path.relative_to(found.cassettes)}")
    return done.returncode


def _stamps(directory: Path) -> dict[Path, tuple[int, int]]:
    """Each cassette's modification time and size: what a recording changed."""
    return {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in directory.rglob("*.json")}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if argv else 2
    if argv[0] != "record":
        return _fail(f"no command {argv[0]!r}: pubtest record", 2)
    return record(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
