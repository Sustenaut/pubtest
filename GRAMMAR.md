# The grammar

Every Sustenaut suite says what it tests in the same words. This file is
those words: the steps pubtest gives every suite, the same in Python
(pytest-bdd) and Node (cucumber-js and quickpickle). A step here is written
once, tested once against both languages, and imported by every suite.

## The shape of a scenario

A scenario sets something up, takes one action, and checks what came of it.

```gherkin
Scenario: A check with a value it may not show is refused
  Given a scratch directory
  And the secret "canary-7f3e"
  And the file "pubkit.json" holds:
    """
    {"kind": "service", "deploy": {"token": "canary-7f3e"}}
    """
  When I run "pubdeploy check"
  Then it fails
  And stderr mentions "deploy.token"
  And no secret appears in what it produced
```

- **Given** steps build the world. The common setups are pubtest's (files,
  the environment, stand-in programs, fake services, git). A suite adds only
  the setups of its own domain, in the same voice ("a publication with two
  objects").
- **When** is the one action. Running a program or sending a request is
  pubtest's. Calling a project's own code is the suite's step, which leaves
  what came back as the **result** (below).
- **Then** steps check the result, the output, the files, the requests sent
  and the programs run. They are all pubtest's, so a check reads the same in
  every repository.

A scenario has a When (pubkit's TEST-04), however many Givens and Thens it
needs. More steps of pubtest's are better than one step of the suite's that
does the same.

## The result

A suite's own When step does its action through pubtest's context and leaves
what came of it there:

```python
@when(parsers.parse('the planner plans "{week}"'))
def plans(ctx, week):
    ctx.attempt(lambda: planner.plan(week))
```

```js
When("the planner plans {string}", async function (week) {
  await this.attempt(() => planner.plan(week));
});
```

`attempt` keeps the return value as the result, or the error it raised as
the refusal: an exception, a `SystemExit` or a rejected promise. The result
checks below then read either. A program run by `I run` is a result too: its
exit code, stdout and stderr.

## The steps

Quoted values are literal text. `V` is compared as JSON when it reads as
JSON (`2`, `true`, `"x"`, `[1, 2]`) and as text otherwise. A docstring
(`"""`) or a table carries anything longer. Paths are relative to the
scratch directory.

### The result

| Step | Checks |
| --- | --- |
| `Then the result is "V"` | the result equals V |
| `Then the result is:` + docstring | the result equals the JSON (or the text) given |
| `Then the result includes "V"` | text contains it, a list holds it, a map has it as a key |
| `Then the result does not include "V"` | the opposite |
| `Then the result's "K" is "V"` | the value at the dotted key K (`a.b.0`) equals V |
| `Then the result has N items` | the result's length is N (any noun: `N links`, `N emails`) |
| `Then the result is empty` | nothing: `None`, `""`, `[]`, `{}` |
| `Then it is refused, saying "T"` | the action raised, and its message contains T |
| `Then it is refused` | the action raised |
| `Then it is not refused` | the action returned |

### Files

| Step | Does or checks |
| --- | --- |
| `Given a scratch directory` | a fresh directory, the working directory for the scenario; later steps' paths are in it |
| `Given the file "P" holds "T"` | writes one line of text |
| `Given the file "P" holds:` + docstring | writes the text |
| `Given the file "P" is executable` | sets its mode so it runs |
| `Given the file "P" is removed` | deletes it, or a directory and what it holds |
| `When the file "P" changes to:` + docstring | rewrites it, as a person would between two runs |
| `Then the file "P" exists` / `does not exist` | |
| `Then the file "P" holds "T"` | its whole text, less a final newline, is T |
| `Then the file "P" holds:` + docstring | its whole text is the docstring |
| `Then the file "P" includes "T"` / `does not include "T"` | |
| `Then the file "P" includes "T" once` | exactly one line holds T |
| `Then the JSON in "P" is:` + docstring | the file parses to the JSON given |
| `Then the JSON in "P" has "K" equal to "V"` | the value at the dotted key K |
| `Then nothing was written` | no file in the scratch directory was made, changed or removed since its Given |

### The environment

| Step | Does |
| --- | --- |
| `Given the environment sets "N" to "V"` | for the scenario, restored after |
| `Given the environment does not set "N"` | removes it for the scenario |

### Programs

| Step | Does or checks |
| --- | --- |
| `Given the program under test is "NAME"` | `NAME` in later `I run` steps is the built program from `<NAME>_BIN_DIR`, never from PATH |
| `When I run "CMD"` | runs CMD (split as a shell splits it) in the scratch directory, and keeps what it did as the result |
| `When I run "CMD" with the input:` + docstring | the docstring on its standard input |
| `Then it succeeds` / `it fails` | exit code 0, or not |
| `Then the exit code is N` | |
| `Then it prints "T"` / `it does not print "T"` | stdout contains T, or not |
| `Then it prints:` + docstring | stdout is the docstring |
| `Then stdout is empty` | |
| `Then stderr mentions "T"` / `stderr does not mention "T"` | |

### Stand-in programs

A stand-in is a script put first on PATH in place of a real program, which
records each run. It is how a suite tests what drives kubectl, ssh, git or
gcloud without reaching them.

| Step | Does or checks |
| --- | --- |
| `Given a stand-in "NAME"` | succeeds and prints nothing |
| `Given a stand-in "NAME" that prints "T"` | |
| `Given a stand-in "NAME" that prints:` + docstring | |
| `Given a stand-in "NAME" that fails, saying "T"` | exits 1 with T on stderr |
| `Given only stand-ins are installed` | PATH holds the stand-ins and the system's basic tools, so any other program is missing |
| `Given "NAME" is not installed` | |
| `Then "NAME" was run with "ARGS"` | some run had exactly these arguments |
| `Then "NAME" was run N times` | |
| `Then "NAME" was not run` | |
| `Then nothing was run` | no stand-in ran |

### HTTP: a service under test

A suite tells pubtest how to send its service a request: a `http_client`
fixture in Python, `this.request` in Node, given a method, a path, headers
and a body, and answering a status, headers and a body. A Starlette or
FastAPI app, a WSGI app and a Cloudflare Worker's `fetch` each have an
adapter.

| Step | Does or checks |
| --- | --- |
| `Given I am signed in as "EMAIL"` | sends the email in the identity header (X-Forwarded-Email unless the suite names another) |
| `Given I am not signed in` | |
| `Given requests come from "ORIGIN"` | sets Origin |
| `When I GET "PATH"` | the answer is the result |
| `When I POST to "PATH" with:` + docstring | a JSON body |
| `When I POST to "PATH" with the form:` + table | a form body |
| `When I send "METHOD" to "PATH"` | |
| `Then the answer is N` | the status |
| `Then the answer's "H" is "V"` | a header |
| `Then the answer has no "H"` | |
| `Then the answer includes "T"` / `does not include "T"` | the body |
| `Then the answer includes "T" once` | one line of the body holds T |
| `Then the answer is the JSON:` + docstring | |
| `Then the answer redirects to "PATH"` | 3xx with Location |

### HTTP: fake services the code calls

| Step | Does or checks |
| --- | --- |
| `Given a fake "NAME" service` | an HTTP server on 127.0.0.1, its address in `NAME_URL` for the scenario, that answers 404 to anything it was not told |
| `Given the "NAME" service answers "METHOD PATH" with N` | |
| `Given the "NAME" service answers "METHOD PATH" with N and:` + docstring | the body |
| `Then the "NAME" service was asked "METHOD PATH"` | |
| `Then the "NAME" service was sent:` + docstring | some request's body was this JSON |
| `Then the "NAME" service was asked nothing` | |
| `Then nothing was sent` | no fake service was asked anything |

### Recorded answers

| Step | Does or checks |
| --- | --- |
| `Given the answers recorded in "DIR"` | requests to the services they name are answered from those files, in order |
| `Then every recorded answer was used` | |

### Secrets

| Step | Checks |
| --- | --- |
| `Given the secret "V"` | V is a value that must never show |
| `Then no secret appears in what it produced` | not in stdout or stderr, the result or the refusal, any file written, any stand-in's arguments or any request sent |

### Git

| Step | Does |
| --- | --- |
| `Given a git repository` | in the scratch directory, with one commit on main |
| `Given a commit tagged "T"` | commits what is there and tags it |
| `Given the branch "B"` | made at the current commit, and checked out |

## What a suite writes itself

- Givens for its own domain, in this voice: "a publication with two
  objects", not "the fixture publication_two is loaded".
- Its own When, through `attempt`, for an action pubtest has no step for.
- Nothing else. A suite step that checks a result is a pubtest step that is
  missing: propose it here first.

## How a step is written

- One sentence, in plain words, with its values as parameters and no
  project's name in it.
- State through the scenario's context (pytest-bdd fixtures, the cucumber
  World), never module globals.
- Everything a step starts (a server, a stand-in, a change to the
  environment, a mock) is undone when the scenario ends, passed or failed.
- The same text means the same check in Python and in Node: pubtest's own
  features run in both.
