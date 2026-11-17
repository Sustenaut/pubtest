"""Steps for python-features/suite-ctx.feature: a suite run with pytester."""

from pytest_bdd import scenarios, then, when

scenarios("../tests/python-features/suite-ctx.feature")

INNER_FEATURE = """Feature: Inner
  Scenario: Inner
    Given a note in the suite's own ctx
    When I run "sh -c 'exit 3'"
    Then it fails
    And the exit code is 3
    And the suite's own ctx still holds its note
"""
INNER_STEPS = '''import pytest
from pytest_bdd import given, scenarios, then

scenarios("inner.feature")


@pytest.fixture
def ctx():
    return {}


@given("a note in the suite's own ctx")
def note(ctx):
    ctx["note"] = "kept"


@then("the suite's own ctx still holds its note")
def still_there(ctx):
    assert ctx["note"] == "kept"
'''


@when("a suite whose ctx is a dict runs a program that fails", target_fixture="inner")
def inner_run(pytester):
    pytester.makefile(".feature", inner=INNER_FEATURE)
    pytester.makepyfile(test_inner=INNER_STEPS)
    pytester.makeini("[pytest]\nbdd_features_base_dir = .\n")
    return pytester.runpytest()


@then("that suite passes")
def inner_passes(inner):
    assert inner.ret == 0, inner.stdout.str()
