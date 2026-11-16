Feature: HTTP: requests to the service under test, and fake services it calls
  The service under test is a small app of the suite's own
  (tests/steps/conftest.py, test/steps): it greets the signed-in person,
  echoes a JSON body, redirects, and fetches from the fake "weather" service.

  Scenario: A signed-in request
    Given I am signed in as "ann@example.org"
    When I GET "/hello"
    Then the answer is 200
    And the answer includes "hello, ann@example.org"
    And the answer includes "hello" once
    And the answer's "content-type" is "text/plain"
    And the answer has no "Set-Cookie"

  Scenario: Not signed in
    Given I am not signed in
    When I GET "/hello"
    Then the answer is 403
    And the answer does not include "hello"

  Scenario: A JSON body
    When I POST to "/echo" with:
      """
      {"a": 1}
      """
    Then the answer is 200
    And the answer is the JSON:
      """
      {"echo": {"a": 1}}
      """

  Scenario: A form
    When I POST to "/form" with the form:
      | field | value |
      | name  | Ann   |
    Then the answer includes "name=Ann"

  Scenario: A redirect is not followed
    When I GET "/old"
    Then the answer redirects to "/new"

  Scenario: A fake service the app calls
    Given a fake "weather" service
    And the "weather" service answers "GET /today" with 200 and:
      """
      {"sky": "clear"}
      """
    When I GET "/forecast"
    Then the answer includes "clear"
    And the "weather" service was asked "GET /today"

  Scenario: A fake service asked nothing
    Given a fake "weather" service
    When I GET "/hello"
    Then the "weather" service was asked nothing
    And nothing was sent
