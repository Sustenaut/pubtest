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
