Feature: The Python adapters reach an ASGI app as they reach a WSGI one
  The same requests as http.feature, to the same service written as an ASGI
  app (Starlette and FastAPI are ASGI apps).

  Background:
    Given the service under test is its ASGI version

  Scenario: A signed-in request, through ASGI
    Given I am signed in as "ann@example.org"
    When I GET "/hello"
    Then the answer is 200
    And the answer includes "hello, ann@example.org"
    And the answer's "Content-Type" is "text/plain"

  Scenario: A JSON body, through ASGI
    When I POST to "/echo" with:
      """
      {"a": 1}
      """
    Then the answer is the JSON:
      """
      {"echo": {"a": 1}}
      """

  Scenario: A redirect, through ASGI, is not followed
    When I GET "/old"
    Then the answer redirects to "/new"
