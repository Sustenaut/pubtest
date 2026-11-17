Feature: Stand-in programs in place of real ones
  A stand-in is first on PATH and records each run, so a suite tests what
  drives a program without running it.

  Background:
    Given a scratch directory

  Scenario: A stand-in's output, and how it was run
    Given a stand-in "kubectl" that prints "pod/web"
    When I run "sh -c 'kubectl get pods -n web'"
    Then it prints "pod/web"
    And "kubectl" was run with "get pods -n web"
    And "kubectl" was run 1 times

  Scenario: A stand-in that fails
    Given a stand-in "gcloud" that fails, saying "permission denied"
    When I run "gcloud auth list"
    Then it fails
    And stderr mentions "permission denied"

  Scenario: A stand-in that answers in turn
    Given a stand-in "kubectl" that answers in turn:
      | args      | exit | stdout     |
      | get *     | 0    | none       |
      | apply *   | 0    | configured |
      | get *     | 0    | pod/web    |
    When I run "sh -c 'kubectl get pods; kubectl apply -f x; kubectl get pods; kubectl get pods'"
    Then it prints "none"
    And it prints "configured"
    And it prints "pod/web"
    And "kubectl" was run 4 times

  Scenario: A program that is not installed is missing
    Given a stand-in "git"
    And "ssh" is not installed
    When I run "sh -c 'command -v ssh || echo missing'"
    Then it prints "missing"
    And "git" was not run

  Scenario: Nothing was run
    Given a stand-in "kubectl"
    When I run "true"
    Then nothing was run
