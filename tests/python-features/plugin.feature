Feature: What the plugin gives a suite besides the steps
  Carried over from pubkit's plugin.feature when the plugin moved here: a
  failing step shows the run, cleanups run in reverse even when a scenario
  fails, feature tags are markers, and a program under test never comes from
  PATH. Each runs a small suite of its own through pytester.

  Scenario: A check that does not hold fails the scenario, showing the run
    Given a suite whose feature reads:
      """
      Feature: echo
        Scenario: wrong text
          When I run "echo hello"
          Then it prints "goodbye"
      """
    When the suite runs
    Then 1 scenario fails
    And the report shows "stdout: 'hello"

  Scenario: Cleanups run in reverse, even when the scenario fails
    Given a suite whose feature reads:
      """
      Feature: cleanup
        Scenario: fails after registering cleanups
          Given cleanups "first" and "second"
          Then it fails anyway
      """
    When the suite runs
    Then 1 scenario fails
    And the cleanups ran as "second,first"

  Scenario: Feature tags are markers, so strict markers and selection work
    Given a suite whose feature reads:
      """
      Feature: tagged
        @browser
        Scenario: slow
          When I run "true"
          Then it succeeds

        Scenario: fast
          When I run "true"
          Then it succeeds
      """
    When the suite runs with "-m" "not browser"
    Then 1 scenario passes
    And 1 scenario is deselected

  Scenario: A program under test with no BIN_DIR variable fails clearly instead of testing PATH
    Given a suite whose feature reads:
      """
      Feature: binary
        Scenario: resolve
          Given the program under test is "tool"
          When I run "tool"
          Then it succeeds
      """
    When the suite runs
    Then 1 scenario fails
    And the report shows "TOOL_BIN_DIR is not set"
