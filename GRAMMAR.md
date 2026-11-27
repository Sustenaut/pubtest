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
inside a value is written `\"`, and a backslash `\\`, in Python as in Node.
Python also takes a bare quote inside a value (`holding "{"kind": "x"}"`) when
no step reads the text with the value ending at an earlier quote; Node's
cucumber expressions don't, so a suite run in both escapes it. A suite writing a step of its own with a
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

### Calls to outside services: faults and counts

With the record/replay harness on ([Record and replay](#record-and-replay)),
each scenario's calls through an integrations `Caller` go through its
transport: a fault put on it, then its cassette. NAME is a plugin's id
(`github.edit-pr`) or what the ids it stands for start with, before a dot
(`github` is every `github.*` plugin). A fault decides every call to NAME it
matches; the first that matches decides, and a call none decides goes to the
cassette.

| Step | Does or checks |
| --- | --- |
| `Given the "NAME" integration can't be reached` | every call to NAME has no answer (`Faulty`'s `no-answer`) |
| `Given the "NAME" integration does not answer in time` | every call to NAME answers slower than its timeout, so it has none; the scenario's clock moves on by the timeout, and nothing waits |
| `Given the "NAME" integration answers "METHOD PATH" with N and:` + docstring | each such call to NAME answers N with that body; PATH is a pattern in which `*` is anything |
| `Given the "NAME" integration answers with N, then as recorded` | the first call to NAME answers N, with no body; the next are answered by the cassette |
| `Given the "NAME" integration answers with what is not JSON` | each call to NAME answers the recorded answer's first half, then text no parser reads |
| `Given the cassette of "SCENARIO"` | the scenario replays another's cassette ("FILE.feature: TITLE", or a TITLE of this feature's), as a fault scenario does over the recording of the scenario it breaks. It never records, and its unused calls are not checked. The tag `@cassette:STEM/SLUG`, the other's cassette path without `.json`, does the same: a tag holds no space |
| `Then the Caller slept N seconds` | the Callers waited N seconds between tries, in all (N may have a fraction) |
| `Then "NAME" was called N times` | calls to NAME, each try counted |

The clock: in replay a scenario's Callers sleep on its clock, which moves on
and never waits, as `Faulty`'s slow answers move it, and their jitter is half
its range, so a call tried four times waits 0.5 + 1 + 2 seconds. In Python
every `Caller` made during the scenario gets that clock, sleep and jitter by
default; in Node a suite passes them, `new Caller(repo, app,
callerOptions(ctx))` (`@sustenaut/pubtest/cassettes`), since integrations'
JS Caller has no default to set. In record mode a sleep waits.

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

## Record and replay

A suite that calls outside services through integrations' `Caller` replays
their answers: one cassette per scenario, in integrations' format
(`integrations.cassette/1`, with its `current` and `baseline`), recorded by
running the scenario against the real services.

**On or off.** The harness is on when integrations is installed (Python:
`integrations.transports` imports: the suite's own pin of it; Node: `@sustenaut/integrations`, an optional peer) and
the repository turns it on in pubrules.json:

```json
"pubtest": {"cassettes": true}
```

`true` keeps cassettes in the data repository, `../<repo>-data/` beside the
repository, private, under `integrations/cassettes/`; a path, such as
`"tests/cassettes"`, keeps them in the repository itself. That form is only for
a suite whose record transport is a stand-in, as the harness's own scenarios'
inner suites (in integrations' suite) are: what real services answered
belongs in the private data repository, and a recording through the real
network into a directory pubrules.json names warns that it does.
`PUBTEST_CASSETTES=1`
turns it on whatever pubrules.json says, and `0` off. Off, nothing here
happens, and the steps above fail saying so.

**Modes.** A session replays, unless `PUBTEST_RECORD=1`, when it records. The
harness sets, for the session and every program it runs:

| Variable | Value |
| --- | --- |
| `PUBTEST_RUN` | the run's id: integrations refuses every call in a mode other than live without it |
| `INTEGRATIONS_MODE` | `replay` or `record` |
| `INTEGRATIONS_CASSETTES` | the cassettes directory, which every cassette must be inside |
| `INTEGRATIONS_CASSETTE` | the scenario's cassette, for a program it runs; while recording, a file of the program's own |
| `INTEGRATIONS_CASSETTE_REPORT` | where a program it runs writes which recorded calls it used |
| `PYTHONPATH`, `NODE_OPTIONS` | load pubtest's report hook (below) into a Python or Node program |

and reads `PUBTEST_ONLY` (a JSON list of scenarios: only they run) and
`PUBTEST_PLAN` (a file each scenario writes whether its cassette is out of
date to), which `pubtest record` sets.

**Where a cassette is.** `INTEGRATIONS_CASSETTES` when it is set, else the
directory pubrules.json names, else the data repository's. In it, a scenario's
cassette is `<feature stem>/<slug>.json`, and an Examples row's
`<feature stem>/<slug>/<row>.json`, the row counted from 1. The slug is the
title (an outline's as written, its `<placeholders>` and all), lower-cased,
each run of anything but a-z and 0-9 one `-`, none at either end. The
scenario is named `FILE.feature: TITLE`, and an Examples row
`FILE.feature: TITLE #ROW`: the name in a cassette's `scenario`, in each
message, and what `pubtest record` takes (or the title alone, or the stem in
place of the file name).

**Each scenario.** In replay it runs on `use(Cassette(...))`, under the faults
its Givens put on it (`Faulty`), its cassette read at its first call. When it
passes, a recorded call that neither it nor a program it ran made fails it, as
does a call that had no recording, even one the code caught. In record mode it
runs on `use(Recorder(network, ...))`, saved when it passes: a scenario that
made no call has no cassette (its old one goes), and a program it ran that
made the calls gives the scenario its recording. Both it and a program making
calls is refused: a cassette holds one process's calls. A recording keeps,
in `current.recorded`, the integrations release, the consumer (`<repo>@<commit>`)
and, under `pubtest`, the hash of the scenario's text (each step's text,
docstring and table), the hash of its step code (Python: each step function's
source; Node: every file of the suite's support code under features/, test/
and tests/), and the names its test customers gave.

**Programs a scenario runs.** A program learns its cassette from
`INTEGRATIONS_MODE` and `INTEGRATIONS_CASSETTE`. At exit, a Python or Node
program that replayed calls appends to `INTEGRATIONS_CASSETTE_REPORT` which
recorded calls it used, how many calls it made and how many were answered: a
`sitecustomize` pubtest puts first on `PYTHONPATH` (it runs the program's own
sitecustomize after it), and a module `NODE_OPTIONS=--import` loads, which
answers the program's calls through a Cassette of its own. A program run with
`python -I` or `-S`, or in another language, is not reported, and the faults a
scenario's Givens put on its transport do not reach a program.

**Errors.**

| Message | When |
| --- | --- |
| ``no data repo: `pubtest record --all` creates it`` | at the start of a replay with no cassettes directory |
| ``no cassette for SCENARIO: record it (`pubtest record "SCENARIO"`)`` | the scenario made a call, and has no cassette |
| `no recorded call in SCENARIO for …`, then the nearest recorded call and how it differs | integrations' `NoSnapshot`: a call its cassette has no recording of |
| `N recorded calls in SCENARIO never made:` | when it passes, the calls no process made |
| `N calls a program made had no recording in SCENARIO` | a program's calls its cassette could not answer |
| `ModeError`, `CassettePathError`, `SecretInRecording` | integrations': a mode without its variables, a cassette outside the cassettes directory, a secret a recording would hold |

**Test customers.** A package gives the steps and the record-time setup of the
test customers a suite records with (the GitHub one is integrations'): in
Python an entry point in the group `pubtest.customers`, a module (or object)
loaded as a pytest plugin, so its steps are the suite's; in Node an entry of
`register(api, { customers: [...] })`. Each has a `name`, `steps` (Node:
`[kind, expression, (ctx, ...args) => ...]`; Python: its module's own
step functions), `setup(tape)` and `cleanup(tape, names)`. In record mode the
first step that asks for a customer's names (`tape.names_of(name)`; Node
`await ctx.tape.namesOf(name)`) runs its setup, which makes or finds what the
scenario needs and returns the names it stands for, `{"the repository":
"real-name"}`; its cleanup runs when the scenario ends, passed or failed. The
names are kept in the cassette, so replay gives the same ones and runs no
setup, and no cleanup.

**When a scenario ends**, in this order: its calls stop going through its
cassette (or recorder); its cassette is checked, or, recording, saved when it
passed; the scenario's own cleanups run (`ctx.cleanup`, in reverse), then, in
record mode, each customer's cleanup; and only then is the environment the
harness set for the scenario (`INTEGRATIONS_CASSETTE`, `INTEGRATIONS_CASSETTES`,
`INTEGRATIONS_CASSETTE_REPORT`, `PYTHONPATH`, `NODE_OPTIONS`) put back, so a
cleanup's Caller finds `INTEGRATIONS_MODE` with its cassette, as a step's does.
In record mode the cleanups call through the record transport itself: nothing
they call is recorded, or meets a fault the scenario's Givens set. Every cleanup
runs, whether the scenario passed or failed, and one that fails does not stop
the rest. A scenario that passed fails with all of what went wrong, a failed
cleanup's among it; one that failed keeps its own failure as the one it
reports, and what went wrong after it is added, as a warning (Python) or on
stderr (Node).

**`pubtest record`.** A command in the Python package and the npm package:

```sh
pubtest record --all                  # every scenario
pubtest record --changed              # the scenarios whose cassette is out of date
pubtest record "FILE.feature: TITLE"  # these scenarios
pubtest record --rename OLD NEW       # move OLD's cassette to NEW's name; records nothing
```

It runs the repository's suite with `PUBTEST_RECORD=1`, pytest-bdd for a
Python repository and cucumber-js for a Node one (pubrules.json's
`ci.language`, else the command's own language), only the scenarios chosen,
and says which cassettes it wrote. `--changed` first runs the suite in replay
and records each scenario that has no cassette though it makes calls, no
longer fits its cassette, or whose text, step code or integrations release
differ from what its cassette's `current.recorded` says; a scenario that
makes no call is never out of date. With no data repository it prints the
`gh repo create OWNER/<repo>-data --private --clone` it needs and stops;
`--create-data-repo` runs it, then commits the repository's README,
`pubrules.json` (`{"kind": "content"}`) and `integrations.json` (excluding
everything) and pushes them.

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
