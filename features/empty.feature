Feature: An empty quoted value is a value
  Every step with a quoted value takes "" as one: the empty text, in
  Python as in Node.

  Background:
    Given a scratch directory

  Scenario: The environment sets a variable to the empty text
    Given the environment sets "PUBTEST_EMPTY" to ""
    When I run "sh -c 'echo [${PUBTEST_EMPTY-unset}]'"
    Then it prints "[]"
    And it does not print "unset"

  Scenario: An empty text result, and an empty key of a result
    When I give back the text ""
    Then the result is ""
    And the result is empty
    And the result matches ""
    When I describe the release
    Then the result's "note" is ""
    And the result's "note" matches ""

  Scenario: An empty line in a file, from a stand-in and as its arguments
    Given a file "blank.txt" holding ""
    And a stand-in "tool" that prints ""
    When I run "tool"
    Then the file "blank.txt" holds ""
    And it prints ""
    And stderr is empty
    And "tool" was run with ""
    And "tool" was run with arguments matching ""

  Scenario: An escaped quote and an escaped backslash in a quoted value are a quote and a backslash
    Given a file "said.txt" holding "say \"hi\""
    When I run "cat said.txt"
    Then it prints "say \"hi\""
    And the file "said.txt" holds "say \"hi\""
    And the file "said.txt" does not include "\\"
