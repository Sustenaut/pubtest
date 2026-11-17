Feature: A suite with a ctx of its own keeps every pubtest step
  A suite may define a `ctx` fixture of its own (a dict, say), as suites did
  under pubkit's plugin. pubtest's steps then keep their own context apart,
  and lose nothing.

  Scenario: A suite whose ctx is a dict runs a program and reads it
    When a suite whose ctx is a dict runs a program that fails
    Then that suite passes
