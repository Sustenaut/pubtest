Feature: Secrets never show in what an action produced
  A value a Given names as a secret must not appear in stdout or stderr,
  the result or the refusal, a file the action wrote, the arguments it gave
  a program, or a request it sent.

  Background:
    Given a scratch directory
    And the secret "canary-7f3e"

  Scenario: A program that keeps the secret to itself
    Given the environment sets "TOKEN" to "canary-7f3e"
    When I run "sh -c 'test -n \"$TOKEN\" && echo has a token'"
    Then it prints "has a token"
    And no secret appears in what it produced

  Scenario: A secret printed is caught
    Given the environment sets "TOKEN" to "canary-7f3e"
    When I run "sh -c 'echo $TOKEN > leaked.txt'"
    Then the secret is found in "the file leaked.txt"
