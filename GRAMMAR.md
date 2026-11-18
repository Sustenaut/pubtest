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
  And a file "pubrules.json" holding:
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

A scenario has at least one When (pubrules's TEST-04), however many Givens and
Thens it needs. Its action may be a chain (`When I run … And the file "P"
changes to: … And I run …`): an edit between two runs is one action. More
steps of pubtest's are better than one step of the suite's that does the
same.

## The result

Whichever kind of When a scenario takes, what it came to is one record: the
**value** it returned or the **refusal** it raised, its **exit code**, and what
it printed on **stdout** and **stderr**.

- `When I run "CMD"` fills the exit code, stdout and stderr.
- A suite's own When calls `attempt`, which fills the value or the refusal,
  and what the call printed too: code 0 when it returns, 1 when it raises,
  and the code it exits with (`SystemExit` in Python, `process.exit` in
  Node). So a suite that calls its command-line `main(argv)` in-process
  reads it with the same steps as one that runs the program.

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

`attempt` awaits what the action returns when it is awaitable, in Python as
in Node.

A scenario with a second When is checked against the second: each Then reads
what the latest action came to. In Python a suite's own When may instead set
`target_fixture="result"` to a run of its own (a `subprocess.CompletedProcess`,
say), which the program steps then read until pubtest's next `I run`.

**A refusal no step reads fails the scenario.** When the action was refused
and no Then read the refusal (`it is refused…`, `the refusal …`, `it fails`,
`the exit code is N`), the scenario fails when it ends, with the refusal's traceback. A
broken When cannot pass through `the result is empty`.

## The steps

Quoted values are literal text. A step's value `V` is compared by one rule:
**when the result is text, V is compared as text; otherwise V is read as JSON
and compared as a value, and a V that does not read as JSON is compared with
the result's text.** So `the result is "2"` holds for the text `2` and for the
number 2, and `"true"` and `"null"` hold only for those values: a true is
never 1, nor 0 false. The same rule
holds for `includes` and `the result's "K" is "V"`. A dotted key indexes maps
by name and lists by number (`people.0.name`). A docstring (`"""`) or a table
carries anything longer. Paths are relative to the scratch directory.

A quoted value may be empty: `the environment sets "N" to ""` sets N to the
empty text, and `the result's "K" is ""` holds for an empty text. A quote
inside a value is written `\"`. A suite writing a step of its own with a
quoted value in Python can use `pubtest.steps.phrase('… "{name}" …')` in
place of `parsers.parse`, which matches the same way, `""` too.

The YAML steps read YAML with PyYAML in Python and the `yaml` package in
Node, which a suite that uses them installs; pubtest itself needs neither.

### The result

| Step | Checks |
| --- | --- |
| `Then the result is "V"` | the result equals V |
| `Then the result is not "V"` | the result is not V |
| `Then the result is:` + docstring | the result equals the JSON (or the text) given |
| `Then the result is:` + table | the result is a list of maps, one per row, the header row their keys, each cell compared as a V |
| `Then the result includes "V"` | text contains it, a list holds it, a map has it as a key |
| `Then the result does not include "V"` | the opposite |
| `Then the result's "K" is "V"` | the value at the dotted key K (`a.b.0`) equals V |
| `Then the result's "K" includes "T"` | the value at K includes T, as `the result includes` reads it |
| `Then the result's "K" matches "P"` | the value at K is text, and all of it is the pattern P |
| `Then the result has N items` | the result's length is N (any noun: `N links`, `N emails`) |
| `Then the result is empty` | nothing: `None`, `null`, `undefined`, `""`, `[]`, `{}` |
| `Then it is refused, saying "T"` | the action raised, and its message contains T |
| `Then it is refused` | the action raised |
| `Then it is not refused` | the action returned |
| `Then the refusal is a "NAME"` | the action raised, and the refusal's class, or a class it derives from, is NAME: in Python a class in its MRO, by its name or its module's and its name (`builtins.KeyError`); in Node a constructor on its prototype chain |
| `Then the refusal's "K" is "V"` | the value at the dotted key K of the refusal's attributes equals V; `message` is its message |
| `Then the result matches "P"` | the result is text, and all of it is the pattern P (below) |

A **pattern** is literal text in which only `*` is special: it stands for
anything, newlines too, and the pattern must match the whole text (a whole
line, in the line steps). It reads the same in Python and in Node, as a
regular expression would not.

### Files

| Step | Does or checks |
| --- | --- |
| `Given a scratch directory` | a fresh directory, the working directory for the scenario; later steps' paths are in it |
| `Given a file "P" holding "T"` | writes one line of text (a Given's words differ from the Then's: cucumber-js matches a step by its text alone) |
| `Given a file "P" holding:` + docstring | writes the text |
| `Given the file "P" is executable` | sets its mode so it runs |
| `Given the file "P" is removed` | deletes it, or a directory and what it holds; one already gone is fine |
| `Given a file "P" copied from "SRC"` | copies a file or a directory of the repository (the nearest directory holding pubrules.json, from where the suite started) to P: a fixture kept beside the suite. A SRC that is absolute, or that leads out of the repository, is refused |
| `When the file "P" changes to:` + docstring | rewrites it, as a person would between two runs |
| `Then the file "P" exists` / `does not exist` | |
| `Then the file "P" holds "T"` | its whole text, less a final newline, is T |
| `Then the file "P" holds:` + docstring | its whole text is the docstring |
| `Then the file "P" includes "T"` / `does not include "T"` | |
| `Then the file "P" includes "T" once` | exactly one line holds T |
| `Then the JSON in "P" is:` + docstring | the file parses to the JSON given |
| `Then the JSON in "P" has "K" equal to "V"` | the value at the dotted key K |
| `Then the YAML in "P" is:` + docstring | the file's YAML is the docstring's (YAML or JSON); a file of several documents is the list of them |
| `Then the YAML in "P" has "K" equal to "V"` | the value at the dotted key K; in a file of several documents, K starts with the document's number (`1.spec.replicas`) |
| `Then the file "P" can be run` | it is executable (a Then's words differ from the Given's `is executable`) |
| `Then the directory "D" holds:` + docstring | the names in D, one a line, in name order; a directory's ends with `/` |
| `Then nothing was written` | no file in the scratch directory was made, changed or removed since the first When |

### The environment

| Step | Does |
| --- | --- |
| `Given the environment sets "N" to "V"` | for the scenario, restored after |
| `Given the environment does not set "N"` | removes it for the scenario |

### Programs

| Step | Does or checks |
| --- | --- |
| `Given the program under test is "NAME"` | `NAME` in later `I run` steps is the built program from `<NAME>_BIN_DIR`, never from PATH |
| `When I run "CMD"` | runs CMD, split as a shell splits words, in the scratch directory, for at most 120 seconds. Its first word is the program under test of that name when a Given named one (from its `_BIN_DIR`), and otherwise the program found on PATH, stand-ins first |
| `When I run "CMD" with the input:` + docstring | the docstring on its standard input |
| `Then it succeeds` / `it fails` | exit code 0, or not |
| `Then the exit code is N` | |
| `Then it prints "T"` / `it does not print "T"` | stdout contains T, or not |
| `Then it prints:` + docstring | stdout is the docstring |
| `Then stdout is empty` / `stderr is empty` | |
| `Then stderr mentions "T"` / `stderr does not mention "T"` | |
| `Then it prints the JSON:` + docstring | stdout reads as JSON, and is the docstring's |
| `Then the JSON it prints has "K" equal to "V"` | the value at the dotted key K of what stdout reads as |
| `Then it prints a line matching "P"` | some line of stdout is the pattern P |
| `Then stderr has a line matching "P"` | some line of stderr is the pattern P |
| `Then it prints no line matching "P"` | no line of stdout is the pattern P |
| `Then stderr has no line matching "P"` | no line of stderr is the pattern P |

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
| `Given a stand-in "NAME" that answers in turn:` + table | a row per answer: `args` (a pattern in which only `*` is special, for anything), and optionally `exit`, `stdout`, `stderr`. A run takes the first matching answer not given yet, or the last matching one once all are given |
| `Given a stand-in "NAME" that reads its input` | succeeds, prints nothing, and reads its standard input to the end, as `kubectl apply -f -` does. Only a stand-in that reads waits for its input |
| `Given only stand-ins are installed` | PATH holds the stand-ins and these tools alone, so any other program is missing: sh, bash, env, cat, echo, printf, mkdir, rm, cp, mv, chmod, ls, sed, grep, head, tail, tr, cut, sort, uniq, wc, dirname, basename, mktemp, date, sleep, true, false, test, touch, readlink, realpath, id, uname |
| `Given "NAME" is not installed` | |
| `Then "NAME" was run with "ARGS"` | some run had exactly these arguments |
| `Then "NAME" was run with arguments matching "P"` | some run's arguments, joined by spaces, are the pattern P |
| `Then "NAME" was not run with arguments matching "P"` | no run's arguments are the pattern P |
| `Then "NAME" was run, in order, with arguments matching:` + docstring | a pattern a line: some runs, in this order, match them one by one, though other runs may come between |
| `Then "NAME" read the input:` + docstring | some run of a stand-in that reads read exactly this |
| `Then "NAME" read input including "T"` | |
| `Then "NAME" was run N times` | |
| `Then "NAME" was not run` | |
| `Then nothing was run` | no stand-in ran |

### HTTP: a service under test

The suite constructs the client, since it is the suite that knows its app,
its Worker's bindings or its server; pubtest only calls it. In Python it is
the `http_client` fixture; in Node, `register(api, { client })`. A client
takes a method, a path, headers and a body, and answers a status, headers
(compared without case) and the body as text, its JSON read when a step asks.
It does not follow redirects. The JSON steps send `application/json`, the
form step `application/x-www-form-urlencoded`. pubtest ships adapters for an
ASGI app (Starlette, FastAPI), a WSGI app and a listening server
(`pubtest.http.url(base)`) in Python, and for a `fetch` handler (a
Cloudflare Worker) and a listening server (`fromUrl(base)`) in Node; none
needs a dependency, so a suite that tests no service installs nothing for
them. The ASGI adapter gives the app what a server would: the path
percent-decoded (`raw_path` as sent), a Content-Length with a body, and the
connection kept until the answer is complete, so a streamed answer is read
to its end.

| Step | Does or checks |
| --- | --- |
| `Given I am signed in as "EMAIL"` | sends the email in the identity header (X-Forwarded-Email unless the suite names another) |
| `Given I am not signed in` | |
| `Given requests come from "ORIGIN"` | sets Origin |
| `Given requests carry the header "H" set to "V"` | on every request after it |
| `When I GET "PATH"` | the answer is the result |
| `When I POST to "PATH" with:` + docstring | a JSON body |
| `When I POST to "PATH" with the form:` + table | a form body |
| `When I send "METHOD" to "PATH"` | |
| `When I send "METHOD" to "PATH" with:` + docstring | a JSON body, by any method |
| `When I send "METHOD" to "PATH" with the file "P"` | the file's bytes, as `application/octet-stream` unless a Given set the Content-Type |
| `Then the answer is N` | the status |
| `Then the answer's "H" is "V"` | a header |
| `Then the answer's "H" includes "T"` | the header is there, and holds T |
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
| `Given the "NAME" service answers "METHOD PATH" with N and the header "H" set to "V"` | |
| `Given the "NAME" service answers "METHOD PATH" with N, the header "H" set to "V", and:` + docstring | the header and the body |
| `Then the "NAME" service was asked "METHOD PATH"` | |
| `Then the "NAME" service was asked "METHOD PATH" N times` | |
| `Then the "NAME" service was asked "METHOD PATH" with the header "H" set to "V"` | some such request carried it |
| `Then the "NAME" service was asked "METHOD PATH" without the header "H"` | it was asked that, and no such request carried H |
| `Then every request to the "NAME" service carried the header "H" set to "V"` | it was asked something, and every request carried it |
| `Then the "NAME" service was sent:` + docstring | some request's body was this JSON |
| `Then the "NAME" service was asked nothing` | |
| `Then nothing was sent` | no fake service was asked anything |

### Recorded answers

| Step | Does or checks |
| --- | --- |
| `Given the answers recorded in "DIR"` | each JSON file in DIR, in name order, is one answer, `{"service", "method", "path", "status", "body"}`: the fake service it names (made if need be) answers that request with it |
| `Then every recorded answer was used` | |

### Secrets

| Step | Checks |
| --- | --- |
| `Given the secret "V"` | V is a value that must never show |
| `Then no secret appears in what it produced` | not in stdout or stderr, the result or the refusal, the answer, any file written since the first When, any stand-in's arguments or any request sent to a fake service. A secret given to a program through its environment is how it should reach it, and is not a leak |

### Git

| Step | Does or checks |
| --- | --- |
| `Given a git repository` | in the scratch directory, with one commit on main |
| `Given a commit tagged "T"` | commits what is there and tags it |
| `Given the branch "B"` | made at the current commit, and checked out |
| `Given everything is committed with the message "T"` | |
| `Given a bare remote "NAME"` | a bare repository outside the scratch directory, added as the remote NAME, with the current branch pushed to it |
| `Then the last commit's message includes "T"` | |
| `Then the working tree is clean` | nothing changed or untracked |
| `Then the tag "T" exists` | |
| `Then the remote "NAME" has the branch "B"` | |

## What a suite writes itself

- Givens for its own domain, in this voice: "a publication with two
  objects", not "the fixture publication_two is loaded".
- Its own When, through `attempt`, for an action pubtest has no step for.
  A frozen clock and a Worker's scheduled event are the suite's own too,
  since each project reads the time and is scheduled its own way.
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
