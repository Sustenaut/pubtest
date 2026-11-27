# pubtest

The Gherkin steps every Sustenaut suite shares. One grammar,
[GRAMMAR.md](GRAMMAR.md), shipped two ways:

- **`pubtest`**, a Python package: a pytest-bdd plugin that loads into every
  pytest session.
- **`@sustenaut/pubtest`**, an npm package: the same steps for cucumber-js and
  quickpickle.

A suite writes the Givens of its own domain and its own When. Everything a
scenario checks, and the setups that repeat across repositories (files, the
environment, programs and stand-ins for them, HTTP, fake services, recorded
answers, secrets, git), are pubtest's, in the same words everywhere. The same
features run against both packages, under pytest-bdd, cucumber-js and
quickpickle, so a step means the same in Python and in Node.

## Python

pubrules's managed `tests/requirements-pubrules.txt` pins pubtest for every
repository, so a suite only writes steps:

```python
from pytest_bdd import parsers, scenarios, when

scenarios("planner.feature")


@when(parsers.parse('the planner plans "{week}"'))
def plans(ctx, week):
    ctx.attempt(lambda: planner.plan(week))
```

```gherkin
Scenario: A week with no work is refused
  Given a scratch directory
  When the planner plans "2026-W53"
  Then it is refused, saying "no such week"
```

Besides the steps, the plugin gives a suite `ctx` (the scenario's context:
`attempt`, `cleanup`, the result), `binary(name)` (a program under test from
`<NAME>_BIN_DIR`, never PATH), `run(...)`, a marker for every `@tag` in the
feature files, and Hypothesis's examples per property from `PUBRULES_FUZZ_RUNS`.
A suite that tests a service gives pubtest its client:

```python
import pubtest.http

@pytest.fixture
def http_client():
    return pubtest.http.asgi(create_app())   # or .wsgi(app), or .url("http://127.0.0.1:8000")
```

## Node

```sh
npm install --save-dev --save-exact github:Sustenaut/pubtest#v0.1.0
```

```js
// features/support/steps.js, for cucumber-js
import * as cucumber from "@cucumber/cucumber";
import { register } from "@sustenaut/pubtest";
import { fromFetch } from "@sustenaut/pubtest/http";
import worker from "../../src/worker.js";

register(cucumber, { client: () => fromFetch((request) => worker.fetch(request, env)) });

cucumber.When("the planner plans {string}", function (week) {
  return this.attempt(() => planner.plan(week));
});
```

For quickpickle, pass its module and `{ runner: "quickpickle" }`, and load the
file through vitest's `setupFiles`.

## Record and replay

A suite that calls outside services through integrations' `Caller` replays
what they answered: one cassette per scenario, recorded with
`pubtest record`, in the data repository beside the repository
(`../<repo>-data/integrations/cassettes/`). Turn it on in pubrules.json:

```json
"pubtest": {"cassettes": true}
```

and install integrations beside pubtest: the suite's own pin of it in Python,
`@sustenaut/integrations` (an optional peer) in Node. pubtest itself never
depends on integrations, whose own suite runs on pubtest. Then:

```sh
pubtest record --all          # record every scenario's calls
pubtest record --changed      # only those whose cassette is out of date
```

and the failure steps (`Given the "github" integration can't be reached`)
break a scenario's calls on purpose, over its cassette. GRAMMAR.md, "Record
and replay", has the modes, variables, paths, errors and test customers.

The harness's end-to-end scenarios (recording, replay, faults, test
customers, under pytest-bdd and cucumber-js) run in integrations' suite,
`tests/features/harness-*.feature`, because they need a real `Caller`, and
pubtest's own tests may not depend on integrations. So a change to the
harness (`cassettes.py`, `js/cassettes.js`, `_child/`, the integration
steps, `pubtest record`) is proven there before it is released: install this
branch in an integrations checkout (`pip install -e <pubtest>` and
`npm install <pubtest>` in clients/js), run `make check` and clients/js'
`npm test`, and say so in the change row. The nightly's integrations pull
request proves it again once released.
For the same reason pubtest's SonarQube coverage leaves out the harness's own
modules (`cassettes.py`, `cli.py`, `_child/`, `steps/integrations.py`, in
pubrules.json's `sonar-args`): their coverage is integrations' suite's.

## Developing

```sh
make venv && npm ci --ignore-scripts
make functional      # the features under pytest-bdd, with coverage
npm test             # the same features under cucumber-js, then quickpickle
```

`features/` is the library's own suite, the steps a suite would write are in
`tests/conftest.py` and `test/suite.js` (the same texts in both), and
`tests/python-features/` holds the Python-only adapter scenarios. The suite
runs without integrations, so the record/replay harness is off in it (see
"Record and replay" for where its scenarios run). A change to
a step changes GRAMMAR.md, both packages and a feature, in one pull request,
and records itself with `pubrel add`. Releases are cut with `pubrel prepare`
from a checkout whose `corpus/.publet` holds the release key.

## Licence

Apache-2.0.
