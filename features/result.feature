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
