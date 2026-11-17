Feature: A refusal no step reads fails the scenario
  When an action is refused and no Then reads the refusal (it is refused,
  it fails, the exit code), the scenario fails when it ends, so a broken
  When cannot pass through a check that reads the result.

  Scenario: A refusal no step reads fails the scenario
    When a scenario whose action is refused, and that reads no refusal, runs
    Then that scenario fails, saying "no step read it"

  Scenario: A refusal a step reads does not
    When a scenario whose action is refused, and that reads the refusal, runs
    Then that scenario passes
