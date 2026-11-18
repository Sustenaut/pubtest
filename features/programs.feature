Feature: Programs, run as a person runs them
  `I run` runs a command in the scratch directory. Its first word is the
  program under test of that name when a Given named one (from its
  _BIN_DIR, never PATH), and otherwise the program found on PATH.

  Background:
    Given a scratch directory

  Scenario: A program that succeeds, and what it printed
    Given the program under test is "greet"
    When I run "greet Ann"
    Then it succeeds
    And it prints "hello, Ann"
    And it does not print "Ben"
    And it prints:
      """
      hello, Ann
      """

  Scenario: A program that fails says why on stderr
    Given the program under test is "greet"
    When I run "greet"
    Then it fails
    And the exit code is 2
    And stderr mentions "a name"
    And stderr does not mention "hello"
    And stdout is empty

  Scenario: Its standard input
    When I run "cat" with the input:
      """
      typed in
      """
    Then it prints "typed in"

  Scenario: The environment, for the scenario
    Given the environment sets "GREETING" to "hi"
    And the environment does not set "HOME_GREETING"
    When I run "sh -c 'echo $GREETING ${HOME_GREETING:-none}'"
    Then it prints "hi none"

  Scenario: Output as JSON
    Given a file "out.json" holding:
      """
      {"kind": "service", "tags": ["a", "b"]}
      """
    When I run "cat out.json"
    Then it prints the JSON:
      """
      {"tags": ["a", "b"], "kind": "service"}
      """
    And the JSON it prints has "tags.1" equal to "b"

  Scenario: Lines matched, on stdout and stderr
    Given a file "log.txt" holding "released v1.2.3 at 12:00"
    When I run "sh -c 'cat log.txt; echo warning: disk 91% full >&2'"
    Then it prints a line matching "released v* at *"
    And stderr has a line matching "warning: * full"

  Scenario: No line matched, and nothing on stderr
    Given a file "log.txt" holding "released v1.2.3"
    When I run "cat log.txt"
    Then stderr is empty
    And it prints no line matching "failed*"
    And stderr has no line matching "*"
