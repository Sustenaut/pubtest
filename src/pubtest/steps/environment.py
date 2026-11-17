"""The environment, for the scenario only."""

from __future__ import annotations

from pytest_bdd import given, parsers


@given(parsers.parse('the environment sets "{name}" to "{text}"'))
def sets(monkeypatch, name, text):
    monkeypatch.setenv(name, text)


@given(parsers.parse('the environment does not set "{name}"'))
def unsets(monkeypatch, name):
    monkeypatch.delenv(name, raising=False)
