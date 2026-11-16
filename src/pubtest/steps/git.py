"""Git: a repository in the scratch directory."""

from __future__ import annotations

import os
import subprocess

from pytest_bdd import given, parsers

GIT_ENV = {"GIT_AUTHOR_NAME": "pubtest", "GIT_AUTHOR_EMAIL": "pubtest@example.org",
           "GIT_COMMITTER_NAME": "pubtest", "GIT_COMMITTER_EMAIL": "pubtest@example.org"}


def git(ctx, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=ctx.directory or os.getcwd(), capture_output=True, text=True,
                          env={**os.environ, **GIT_ENV}, check=True)
    return done.stdout.strip()


@given("a git repository")
def repository(ctx):
    git(ctx, "init", "-q", "-b", "main")
    git(ctx, "commit", "-q", "--allow-empty", "-m", "start")


@given(parsers.parse('a commit tagged "{tag}"'))
def commit_tagged(ctx, tag):
    git(ctx, "add", "-A")
    git(ctx, "commit", "-q", "--allow-empty", "-m", tag)
    git(ctx, "tag", tag)


@given(parsers.parse('the branch "{branch}"'))
def branch(ctx, branch):
    git(ctx, "switch", "-q", "-c", branch)
