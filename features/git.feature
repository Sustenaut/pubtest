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

  Scenario: Commits, and a remote the program pushes to
    Given a file "a.txt" holding "x"
    And everything is committed with the message "add a"
    And a bare remote "origin"
    When I run "git push -q origin main:release"
    Then it succeeds
    And the remote "origin" has the branch "release"
    And the remote "origin" has the branch "main"
    And the last commit's message includes "add a"
    And the working tree is clean

  Scenario: A tag the program makes
    When I run "git tag v2.0.0"
    Then the tag "v2.0.0" exists
