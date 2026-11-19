Feature: The result: what an action came to, checked in the same words everywhere
  A suite's own When does its action through attempt, which keeps what it
  returned, or what it raised, and what it printed. These scenarios use a
  small suite of their own (tests/steps, test/steps) with the same step texts
  in Python and Node.

  Scenario: A returned value is the result
    When I add 2 and 3
    Then it is not refused
    And the result is "5"

  Scenario: A text result is compared as text
    When I give back the text "2"
    Then the result is "2"
    And the result is not the number 2

  Scenario: A number is not a true, and a true is not a number
    When I add 1 and 0
    Then the result is "1"
    And the result is not "true"

  Scenario: A true is only true
    When I check that 2 is more than 1
    Then the result is "true"
    And the result is not "1"

  Scenario: A structure is compared as JSON
    When I list the words of "b a c"
    Then the result is:
      """
      ["b", "a", "c"]
      """
    And the result includes "a"
    And the result does not include "d"
    And the result has 3 words

  Scenario: A list of records is checked by a table
    When I list the people
    Then the result is:
      | name | age |
      | Ann  | 30  |
      | Ben  | 41  |

  Scenario: A key of the result, by a dotted path
    When I list the people
    Then the result's "1.name" is "Ben"
    And the result's "0.age" is "30"

  Scenario: Nothing is empty
    When I find nothing
    Then the result is empty

  Scenario: A refusal says why
    When I divide 1 by 0
    Then it is refused, saying "division by zero"

  Scenario: An exit is a refusal with its code; what it printed is kept, and says why
    When I run main with "--bad"
    Then it is refused, saying "no such option: --bad"
    And the exit code is 2
    And stderr mentions "usage:"

  Scenario: A text result matched
    When I give back the text "build 42 passed"
    Then the result matches "build * passed"
    And the result matches "*"

  Scenario: A key of the result, included or matched
    When I describe the release
    Then the result's "tags" includes "lts"
    And the result's "version" includes "1.2"
    And the result's "version" matches "v*.*.3"

  Scenario: A refusal's class, a class it derives from, and its fields
    When I look up "colour"
    Then the refusal is a "NotFound"
    And the refusal is a "Problem"
    And the refusal's "key" is "colour"
    And the refusal's "detail.code" is "404"
    And the refusal's "message" is "no colour"

  Scenario: A second action is the one later steps read
    When I run "echo first"
    Then it prints "first"
    When I run main with "Ann"
    Then it succeeds
    And it prints "ok"
    And it does not print "first"
