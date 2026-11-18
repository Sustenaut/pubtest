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

  Scenario: How a fake service was asked, and a header it answers with
    Given a fake "weather" service
    And the "weather" service answers "GET /today" with 200 and the header "X-Sky" set to "clear"
    When I GET "/forecast"
    Then the answer's "X-Sky" is "clear"
    And the "weather" service was asked "GET /today" 1 times
    And the "weather" service was asked "GET /today" with the header "X-Client" set to "pubtest-app"

  Scenario: A file's bytes, by any method, with a header the requests carry
    Given requests carry the header "X-Token" set to "t-1"
    And a scratch directory
    And a file "photo.bin" holding "not really a photo"
    When I send "PUT" to "/upload" with the file "photo.bin"
    Then the answer is 200
    And the answer includes "PUT application/octet-stream 19 t-1"

  Scenario: A JSON body, by any method
    When I send "PUT" to "/echo" with:
      """
      {"a": 2}
      """
    Then the answer is the JSON:
      """
      {"echo": {"a": 2}}
      """

  Scenario: A fake service's header and body together, and the headers it was sent
    Given a fake "weather" service
    And the "weather" service answers "GET /today" with 200, the header "X-Sky" set to "clear", and:
      """
      {"sky": "clear"}
      """
    When I GET "/forecast"
    Then the answer's "X-Sky" is "clear"
    And the answer's "content-type" includes "text"
    And the answer includes "clear"
    And the "weather" service was asked "GET /today" without the header "Authorization"
    And every request to the "weather" service carried the header "X-Client" set to "pubtest-app"
