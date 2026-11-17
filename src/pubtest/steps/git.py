"""Git: a repository in the scratch directory, its remotes, and what was
committed."""

from __future__ import annotations

import os
import subprocess

from pytest_bdd import given, parsers, then

GIT_ENV = {"GIT_AUTHOR_NAME": "pubtest", "GIT_AUTHOR_EMAIL": "pubtest@example.org",
           "GIT_COMMITTER_NAME": "pubtest", "GIT_COMMITTER_EMAIL": "pubtest@example.org"}


def git(pubtest_ctx, *args: str, cwd: str | os.PathLike[str] | None = None) -> str:
    done = subprocess.run(["git", *args], cwd=cwd or pubtest_ctx.directory or os.getcwd(), capture_output=True,
                          text=True, env={**os.environ, **GIT_ENV}, check=False)
    assert done.returncode == 0, f"git {' '.join(args)}: {done.stderr}"
    return done.stdout.strip()


@given("a git repository")
def repository(pubtest_ctx):
    git(pubtest_ctx, "init", "-q", "-b", "main")
    git(pubtest_ctx, "commit", "-q", "--allow-empty", "-m", "start")


@given(parsers.parse('a commit tagged "{tag}"'))
def commit_tagged(pubtest_ctx, tag):
    git(pubtest_ctx, "add", "-A")
    git(pubtest_ctx, "commit", "-q", "--allow-empty", "-m", tag)
    git(pubtest_ctx, "tag", tag)


@given(parsers.parse('the branch "{branch}"'))
def branch(pubtest_ctx, branch):
    git(pubtest_ctx, "switch", "-q", "-c", branch)


@given(parsers.parse('everything is committed with the message "{message}"'))
def committed(pubtest_ctx, message):
    git(pubtest_ctx, "add", "-A")
    git(pubtest_ctx, "commit", "-q", "--allow-empty", "-m", message)


@given(parsers.parse('a bare remote "{name}"'))
def bare_remote(pubtest_ctx, tmp_path, name):
    """A bare repository outside the scratch directory, added as the remote
    `name`, with the current branch pushed to it."""
    remote = tmp_path / "pubtest-remotes" / f"{name}.git"
    remote.mkdir(parents=True)
    git(pubtest_ctx, "init", "-q", "--bare", "-b", "main", str(remote), cwd=remote.parent)
    git(pubtest_ctx, "remote", "add", name, str(remote))
    git(pubtest_ctx, "push", "-q", name, "HEAD")


@then(parsers.parse('the last commit\'s message includes "{text}"'))
def last_message(pubtest_ctx, text):
    message = git(pubtest_ctx, "log", "-1", "--format=%B")
    assert text in message, f"the last commit's message is {message!r}"


@then("the working tree is clean")
def clean(pubtest_ctx):
    status = git(pubtest_ctx, "status", "--porcelain")
    assert not status, f"the working tree has changes:\n{status}"


@then(parsers.parse('the tag "{tag}" exists'))
def tag_exists(pubtest_ctx, tag):
    tags = git(pubtest_ctx, "tag", "--list").splitlines()
    assert tag in tags, f"the tags are {tags}"


@then(parsers.parse('the remote "{name}" has the branch "{branch}"'))
def remote_has(pubtest_ctx, name, branch):
    heads = git(pubtest_ctx, "ls-remote", "--heads", name, branch)
    assert heads, f"the remote {name} has no branch {branch}"
