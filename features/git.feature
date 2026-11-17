Feature: A git repository in the scratch directory

  Background:
    Given a scratch directory
    And a git repository

  Scenario: Tags and branches
    Given a file "a.txt" holding "x"
    And a commit tagged "v1.0.0"
    And the branch "edit"
    When I run "git describe --tags"
    Then it prints "v1.0.0"
    When I run "git branch --show-current"
    Then it prints "edit"
