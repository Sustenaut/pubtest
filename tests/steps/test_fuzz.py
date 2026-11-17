"""Steps for python-features/fuzz.feature: PUBRULES_FUZZ_RUNS, which only the
pytest plugin reads (the steps themselves are in conftest.py)."""

from pytest_bdd import scenarios

scenarios("../tests/python-features/fuzz.feature")
