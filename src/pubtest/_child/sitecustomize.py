"""Loaded by every Python program a pubtest scenario runs (its directory is
first on PYTHONPATH then): at exit, a program that replayed calls from a
cassette writes which recorded calls it used to INTEGRATIONS_CASSETTE_REPORT,
so the scenario fails on a recorded call no process made.

integrations has no hook for this yet, so it reads the Cassette that
`integrations.transports.current_transport()` made from INTEGRATIONS_MODE
(`_by_mode`, private). A sitecustomize of the program's own, further along
sys.path, still runs after this one.
"""

import atexit
import json
import os
import sys


def _report() -> None:
    path = os.environ.get("INTEGRATIONS_CASSETTE_REPORT")
    transports = sys.modules.get("integrations.transports")
    if not path or transports is None:
        return
    for transport in list(getattr(transports, "_by_mode", {}).values()):
        if not isinstance(transport, transports.Cassette):
            continue
        calls = transport.calls
        entry = {"pid": os.getpid(), "language": "python", "cassette": os.environ.get("INTEGRATIONS_CASSETTE"),
                 "calls": len(calls), "used": [i for i, c in enumerate(calls) if c.used],
                 "sent": len(transport.sent), "answered": sum(c.used for c in calls)}
        with open(path, "a", encoding="utf-8") as out:
            out.write(json.dumps(entry) + "\n")


def _chain() -> None:
    """The next sitecustomize on sys.path, which this one would otherwise hide."""
    import importlib.machinery  # noqa: PLC0415
    import importlib.util  # noqa: PLC0415
    here = os.path.dirname(os.path.abspath(__file__))
    rest = [p for p in sys.path if os.path.abspath(p or os.curdir) != here]
    spec = importlib.machinery.PathFinder.find_spec("sitecustomize", rest)
    if spec is not None and spec.loader is not None:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)


atexit.register(_report)
_chain()
