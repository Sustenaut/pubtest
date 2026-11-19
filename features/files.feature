Feature: Files in a scratch directory
  Each scenario that asks for one gets a fresh scratch directory as its
  working directory; paths in the steps are in it.

  Background:
    Given a scratch directory

  Scenario: A file written by a Given is there to check
    Given a file "notes/a.txt" holding "one line"
    When I run "cat notes/a.txt"
    Then it prints "one line"
    And the file "notes/a.txt" exists
    And the file "notes/a.txt" holds "one line"
    And the file "notes/b.txt" does not exist

  Scenario: A docstring is a file's text
    Given a file "config.json" holding:
      """
      {"kind": "service", "name": "web"}
      """
    When I run "cat config.json"
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
    When I run "sort -r list.txt"
    Then the file "list.txt" includes "banana" once
    And it prints:
      """
      cherry
      banana
      apple
      """

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

  Scenario: A removed file is gone, and one never there is removed without complaint
    Given a file "gone.txt" holding "x"
    And the file "gone.txt" is removed
    And the file "never-there.txt" is removed
    When I run "ls"
    Then the file "gone.txt" does not exist
    And it does not print "gone.txt"

  Scenario: A file copied from the repository
    Given a file "fixtures/git.feature" copied from "features/git.feature"
    When I run "cat fixtures/git.feature"
    Then it prints "A git repository in the scratch directory"

  Scenario Outline: A copy from outside the repository is refused
    When I copy "<source>" from the repository
    Then it is refused, saying "is not in the repository"
    And the file "copy" does not exist

    Examples:
      | source              |
      | ../outside.txt      |
      | features/../../x    |
      | /etc/hostname       |

  Scenario: A file the program made runnable, and what a directory holds
    Given a file "tool.sh" holding "#!/bin/sh"
    When I run "sh -c 'chmod +x tool.sh && mkdir -p out/sub && touch out/b.txt out/a.txt'"
    Then the file "tool.sh" can be run
    And the directory "out" holds:
      """
      a.txt
      b.txt
      sub/
      """

  Scenario: YAML, one document or several
    Given a file "deploy.yaml" holding:
      """
      kind: Namespace
      metadata:
        name: web
      ---
      kind: Deployment
      metadata:
        name: web
      spec:
        replicas: 2
      """
    And a file "app.yaml" holding:
      """
      name: web
      ports: [80, 443]
      """
    When I run "cat deploy.yaml"
    Then the YAML in "deploy.yaml" has "1.spec.replicas" equal to "2"
    And the YAML in "deploy.yaml" has "0.kind" equal to "Namespace"
    And the YAML in "app.yaml" is:
      """
      {"name": "web", "ports": [80, 443]}
      """
