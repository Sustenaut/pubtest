"""Steps for python-features/plugin.feature: small suites run with pytester."""

import re

from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../tests/python-features/plugin.feature")

INNER_STEPS = '''import os
from pytest_bdd import given, parsers, scenarios, then

scenarios("inner.feature")


@given(parsers.parse('cleanups "{a}" and "{b}"'))
def cleanups(ctx, a, b):
    log = os.environ["CLEANUP_LOG"]
    for name in (a, b):
        ctx.cleanup(lambda name=name: open(log, "a").write(name + ","))


@then("it fails anyway")
def fails_anyway():
    raise AssertionError("on purpose")
'''


@given("a suite whose feature reads:", target_fixture="inner_dir")
def suite(pytester, docstring):
    pytester.makefile(".feature", inner=docstring)
    pytester.makepyfile(test_inner=INNER_STEPS)
    pytester.makeini("[pytest]\nbdd_features_base_dir = .\naddopts = --strict-markers\n")
    return pytester.path


@when("the suite runs", target_fixture="inner")
def runs(pytester, inner_dir, monkeypatch):
    monkeypatch.setenv("CLEANUP_LOG", str(inner_dir / "cleanups.log"))
    monkeypatch.delenv("TOOL_BIN_DIR", raising=False)
    return pytester.runpytest()


@when(parsers.parse('the suite runs with "{a}" "{b}"'), target_fixture="inner")
def runs_with(pytester, a, b):
    return pytester.runpytest(a, b)


@then(parsers.parse("{count:d} scenario {outcome}"))
def outcome(inner, count, outcome):
    word = {"passes": "passed", "fails": "failed", "is deselected": "deselected"}[outcome]
    assert re.search(rf"\b{count} {word}\b", inner.stdout.str()), inner.stdout.str()


@then(parsers.parse('the report shows "{text}"'))
def report_shows(inner, text):
    assert text in inner.stdout.str(), inner.stdout.str()


@then(parsers.parse('the cleanups ran as "{order}"'))
def cleanups_ran(inner_dir, order):
    assert (inner_dir / "cleanups.log").read_text().rstrip(",") == order
