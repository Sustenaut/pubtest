Feature: CI sets the examples each property runs
  PUBRULES_FUZZ_RUNS, which pubrules' CI sets, is how many examples each
  Hypothesis property runs, with no deadline. Unset, Hypothesis keeps its own
  settings.

  Scenario: PUBRULES_FUZZ_RUNS sets the examples per property
    When a suite with one property runs with PUBRULES_FUZZ_RUNS at "7"
    Then that property ran 7 examples

  Scenario: A PUBRULES_FUZZ_RUNS that is not a count is refused
    When a suite with one property runs with PUBRULES_FUZZ_RUNS at "many"
    Then that suite is refused, saying "PUBRULES_FUZZ_RUNS must be a positive whole number"
