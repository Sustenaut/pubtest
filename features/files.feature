Feature: Files in a scratch directory
  Each scenario that asks for one gets a fresh scratch directory as its
  working directory; paths in the steps are in it.

  Background:
    Given a scratch directory

  Scenario: A file written by a Given is there to check
    Given a file "notes/a.txt" holding "one line"
    Then the file "notes/a.txt" exists
    And the file "notes/a.txt" holds "one line"
    And the file "notes/b.txt" does not exist

  Scenario: A docstring is a file's text
    Given a file "config.json" holding:
      """
      {"kind": "service", "name": "web"}
      """
    Then the JSON in "config.json" has "kind" equal to "service"
    And the JSON in "config.json" is:
      """
      {"name": "web", "kind": "service"}
      """
    And the file "config.json" includes "web"
    And the file "config.json" does not include "worker"

  Scenario: A line counted once
    Given a file "list.txt" holding:
      """
      apple
      banana
      cherry
      """
    Then the file "list.txt" includes "banana" once

  Scenario: Nothing was written by a program that only reads
    Given a file "a.txt" holding "x"
    When I run "cat a.txt"
    Then nothing was written
    And it prints "x"

  Scenario: A program that writes is caught writing
    When I run "sh -c 'echo y > b.txt'"
    Then the file "b.txt" holds "y"

  Scenario: A file changed between two runs
    Given a file "a.txt" holding "x"
    When I run "cat a.txt"
    And the file "a.txt" changes to:
      """
      z
      """
    And I run "cat a.txt"
    Then it prints "z"

  Scenario: A removed file is gone
    Given a file "gone.txt" holding "x"
    And the file "gone.txt" is removed
    Then the file "gone.txt" does not exist
