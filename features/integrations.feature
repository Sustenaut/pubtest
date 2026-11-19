Feature: Calls to outside services, replayed and broken on purpose
  pubtest's own suite turns cassettes on (pubrules.json), so a scenario that
  calls through integrations replays its cassette from tests/cassettes/. The
  example client calls github.repo-ops' "call" operation, which is tried up
  to four times; its recordings answer {"name": the URL's last part}. A fault
  is put on the scenario's transport, over its cassette.

  Scenario: A recorded call is answered as it was recorded
    When the example client gets "https://api.github.com/repos/o/r"
    Then the result's "name" is "r"
    And "github.repo-ops" was called 1 times
    And "github" was called 1 times
    And "slack" was called 0 times
    And the Caller slept 0 seconds

  Scenario: An integration that can't be reached is tried again, waiting between tries
    Given the "github" integration can't be reached
    When the example client gets "https://api.github.com/repos/o/r"
    Then it is refused, saying "no answer"
    And "github.repo-ops" was called 4 times
    And the Caller slept 3.5 seconds

  Scenario: An integration that does not answer in time is no answer
    Given the "github.repo-ops" integration does not answer in time
    When the example client gets "https://api.github.com/repos/o/r"
    Then it is refused, saying "timed out"
    And "github.repo-ops" was called 4 times

  Scenario: An answer the fault gives is the code's to read
    Given the "github" integration answers "GET /repos/*/gone" with 404 and:
      """
      {"message": "Not Found"}
      """
    When the example client gets "https://api.github.com/repos/o/gone"
    Then the result's "message" is "Not Found"
    And "github" was called 1 times

  Scenario: After a failed try, the recorded answer
    Given the cassette of "A recorded call is answered as it was recorded"
    And the "github" integration answers with 503, then as recorded
    When the example client gets "https://api.github.com/repos/o/r"
    Then the result's "name" is "r"
    And "github.repo-ops" was called 2 times
    And the Caller slept 0.5 seconds

  @cassette:integrations/a-recorded-call-is-answered-as-it-was-recorded
  Scenario: An answer that is not JSON is refused
    Given the "github" integration answers with what is not JSON
    When the example client gets "https://api.github.com/repos/o/r"
    Then it is refused

  Scenario: A test customer's names are the ones it was recorded with
    Given the example customer's repository "the repository"
    When the example client gets the repository "the repository"
    Then the result's "name" is "pubtest-example-1"
