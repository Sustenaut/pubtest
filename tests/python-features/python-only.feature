Feature: What only the Python side has
  A server already listening reached by pubtest.http.url, a suite's own
  When that sets the result fixture, and a refusal's class named with its
  module.

  Scenario: A server already listening, its redirect not followed
    Given a fake "site" service
    And the "site" service answers "GET /old" with 302 and the header "Location" set to "/new"
    And the service under test is the "site" service, listening
    When I GET "/old"
    Then the answer redirects to "/new"
    And the "site" service was asked "GET /old" 1 times

  Scenario: A server already listening is sent the body and the headers
    Given a fake "site" service
    And the "site" service answers "POST /echo" with 201, the header "X-Kind" set to "echo", and:
      """
      {"ok": true}
      """
    And requests carry the header "X-Token" set to "t-1"
    And the service under test is the "site" service, listening
    When I POST to "/echo" with:
      """
      {"a": 1}
      """
    Then the answer is 201
    And the answer's "X-Kind" is "echo"
    And the answer is the JSON:
      """
      {"ok": true}
      """
    And the "site" service was sent:
      """
      {"a": 1}
      """
    And every request to the "site" service carried the header "X-Token" set to "t-1"

  Scenario: A suite's own When that sets the result fixture is what the checks read
    When the suite's own step runs "echo own" and keeps what it did
    Then it succeeds
    And it prints "own"
    When I run "echo again"
    Then it prints "again"
    And it does not print "own"

  Scenario: A refusal's class, named with its module
    When I divide 1 by 0
    Then the refusal is a "builtins.ZeroDivisionError"
    And the refusal is a "ArithmeticError"
    And the refusal's "message" is "division by zero"

  Scenario: A bare quote inside a quoted value is part of the value, in Python
    Python's steps let a value hold bare quotes, such as a line of JSON,
    where cucumber's {string} needs them escaped.
    Given a scratch directory
    And a file "pubrules.json" holding "{"kind": "utility", "ci": {}}"
    When I run "cat pubrules.json"
    Then the JSON in "pubrules.json" has "kind" equal to "utility"
    And it prints "{"kind": "utility", "ci": {}}"
