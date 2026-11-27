Feature: Record and replay, with integrations not installed
  pubtest never depends on integrations, whose own suite runs on pubtest, so
  pubtest's own suite runs without it. The harness's end-to-end scenarios run
  in integrations' suite (tests/features/harness-*.feature), which installs
  both. Here the harness is off, and its steps say how to turn it on.

  Scenario: A fault step without the harness says how to turn it on
    When I put a fault on "github" without the harness
    Then it is refused, saying "the integration steps need the record/replay harness"
