// Record and replay for a suite's calls to outside services (GRAMMAR.md, "Record
// and replay"): src/pubtest/cassettes.py for Node.
//
// One cassette per scenario, in integrations' format: each scenario runs on
// use(new Cassette(...)) in replay, or use(new Recorder(network, ...)) in record mode,
// saved when it passes. Programs a scenario runs learn their cassette from
// INTEGRATIONS_MODE and INTEGRATIONS_CASSETTE, and say at exit which recorded calls they
// used, so an unused call fails the scenario wherever it was recorded.
//
// @sustenaut/integrations is an optional peer: loaded with import(), and everything
// here is inert unless it loads and the repository turns cassettes on ("pubtest":
// {"cassettes": ...} in pubrules.json, or PUBTEST_CASSETTES=1).
import { createHash, randomInt, randomUUID } from "node:crypto";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { byCodeUnit, onPath } from "./core.js";

export const RECORD = "PUBTEST_RECORD";
export const SWITCH = "PUBTEST_CASSETTES";
export const ONLY = "PUBTEST_ONLY";
export const PLAN = "PUBTEST_PLAN";
export const REPORT = "INTEGRATIONS_CASSETTE_REPORT";
export const RUN = "PUBTEST_RUN";
export const MODE = "INTEGRATIONS_MODE";
export const CASSETTE = "INTEGRATIONS_CASSETTE";
export const CASSETTES = "INTEGRATIONS_CASSETTES";
export const NO_DATA_REPO = "no data repo: `pubtest record --all` creates it";
const CHILD = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "src", "pubtest", "_child");
// Longer than any operation's timeout: slower than this is no answer.
export const NEVER = 86400;

let loaded;

/** integrations' transports.js, or null when @sustenaut/integrations is not installed. */
export async function transports() {
  loaded ??= import("@sustenaut/integrations/transports.js").catch(() => null);
  return loaded;
}

/** A scenario's title as a file name: lower-cased, each run of anything but a-z and 0-9 one "-". */
export function slug(title) {
  return title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "scenario";
}

/** A scenario as a cassette names it: its feature file's name, its title (an outline's,
 * as written) and, for an outline, its Examples row, from 1. */
export class Scenario {
  constructor(feature, title, row = null) {
    Object.assign(this, { feature, title, row: row || null });
  }
  get stem() {
    return this.feature.replace(/\.feature$/, "");
  }
  get id() {
    return `${this.feature}: ${this.title}${this.row ? ` #${this.row}` : ""}`;
  }
  get relative() {
    return this.row ? `${this.stem}/${slug(this.title)}/${this.row}.json` : `${this.stem}/${slug(this.title)}.json`;
  }
  namedBy(selector) {
    const s = selector.trim();
    const names = [this.id, `${this.feature}: ${this.title}`, `${this.stem}: ${this.title}`, this.title, this.relative.replace(/\.json$/, "")];
    if (this.row) names.push(`${this.stem}: ${this.title} #${this.row}`);
    return names.includes(s);
  }
}

/** A scenario from what a person writes: "FILE: TITLE[ #ROW]", or a TITLE of feature's. */
export function parse(selector, feature = null) {
  let text = selector.trim();
  let row = null;
  const m = /^(.*) #(\d+)$/.exec(text);
  if (m) [text, row] = [m[1], Number(m[2])];
  const at = text.indexOf(": ");
  if (at >= 0 && text.slice(0, at).endsWith(".feature")) return new Scenario(text.slice(0, at), text.slice(at + 2), row);
  if (feature === null) throw new Error(`"${selector}" names no feature: write it "FILE.feature: TITLE"`);
  return new Scenario(feature, text, row);
}

function truthy(value) {
  if (value === undefined || value === "") return null;
  return !["0", "false", "no", "off"].includes(value.toLowerCase());
}

function declared(root) {
  try {
    const block = JSON.parse(fs.readFileSync(path.join(root, "pubrules.json"), "utf8"))?.pubtest;
    return block && typeof block === "object" ? block.cassettes : undefined;
  } catch {
    return undefined;
  }
}

/** The harness's settings for the repository at root: as pubtest.cassettes.settings(). */
export async function settings(root, env = process.env) {
  root = path.resolve(root);
  const wanted = truthy(env[SWITCH]) ?? Boolean(declared(root));
  const active = Boolean(wanted) && (await transports()) !== null;
  let cassettes;
  let dataRepo = null;
  const named = declared(root);
  const own = !env[CASSETTES] && typeof named === "string";
  if (env[CASSETTES]) cassettes = path.resolve(env[CASSETTES]);
  else if (own) cassettes = path.resolve(root, named);
  else {
    dataRepo = path.join(path.dirname(root), `${path.basename(root)}-data`);
    cassettes = path.join(dataRepo, "integrations", "cassettes");
  }
  return { active, mode: truthy(env[RECORD]) ? "record" : "replay", root, cassettes, dataRepo, named: own, get recording() { return this.mode === "record"; } };
}

/** At the session's start: refuse a replay with no cassettes at all, make the directory a
 * recording needs, and set the variables every program inherits. */
export function startSession(found) {
  if (!found.active) return;
  if (!fs.existsSync(found.cassettes)) {
    if (found.recording && (found.dataRepo === null || fs.existsSync(found.dataRepo))) fs.mkdirSync(found.cassettes, { recursive: true });
    else throw new Error(`${NO_DATA_REPO} (there is no ${found.cassettes})`);
  }
  process.env[RUN] ??= randomUUID().replaceAll("-", "");
  process.env[MODE] = found.mode;
  process.env[CASSETTES] = fs.realpathSync(found.cassettes);
}

/** The warning a recording gives when it records the real network into pubrules.json's
 * "DIR": that form is for a suite whose record transport is a stand-in (pubtest's own),
 * since the repository is no place for what real services answered. */
export function standInOnly(found, realNetwork) {
  if (!(found.active && found.recording && found.named && realNetwork)) return null;
  return `pubtest record: warning: ${found.cassettes} is pubrules.json's "cassettes": "DIR", which is only for a suite whose record transport is a stand-in; this one records the real network, whose answers belong in the private data repository ("pubtest": {"cassettes": true})`;
}

export function only() {
  return process.env[ONLY] ? JSON.parse(process.env[ONLY]) : null;
}

export function selected(scenario) {
  const chosen = only();
  return chosen === null || chosen.some((s) => scenario.namedBy(s));
}

/** The cassette of scenario in the cassettes directory. */
export function pathFor(scenario, found) {
  return path.join(found.cassettes, scenario.relative);
}

/** NAME is a plugin's id, or what every id it stands for starts with, before a dot. */
export function matchesName(name, plugin) {
  plugin ??= "";
  return plugin === name || plugin.startsWith(`${name}.`);
}

/** The scenario's steps as it runs them: each one's text, docstring and table. */
export function textHash(steps) {
  const lines = [];
  for (const [text, docstring, table] of steps) {
    lines.push(text);
    if (docstring !== null && docstring !== undefined) lines.push(`"""\n${docstring}\n"""`);
    for (const row of table ?? []) lines.push(`| ${row.join(" | ")} |`);
  }
  return sha256(lines.join("\n"));
}

function sha256(text) {
  return createHash("sha256").update(text).digest("hex");
}

function git(root, ...args) {
  const bin = onPath("git");
  if (bin === null) return "";
  const done = spawnSync(bin, args, { cwd: root, encoding: "utf8", timeout: 30_000 });
  return done.status === 0 ? done.stdout.trim() : "";
}

/** <repo>@<commit>: the repository the recording was made from. */
export function consumer(root) {
  const origin = git(root, "remote", "get-url", "origin");
  const name = origin ? origin.replace(/\/+$/, "").split(/[/:]/).pop().replace(/\.git$/, "") : path.basename(root);
  return `${name}@${git(root, "rev-parse", "HEAD") || "uncommitted"}`;
}

/** The integrations release the repository pins: the tag its package.json names. */
export function integrationsVersion(root) {
  try {
    const data = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
    const spec = { ...data.dependencies, ...data.devDependencies, ...data.peerDependencies }["@sustenaut/integrations"] ?? "";
    return /#v?(\d+\.\d+\.\d+)/.exec(spec)?.[1] ?? "unknown";
  } catch {
    return "unknown";
  }
}

/** Every file of the suite's own support code, hashed: Node gives no step's code, so a
 * change to any of it counts as a change to every scenario's steps. */
export function supportHash(root) {
  const files = [];
  const walk = (dir) => {
    for (const entry of fs.existsSync(dir) ? fs.readdirSync(dir, { withFileTypes: true }) : []) {
      if (entry.name === "node_modules" || entry.name.startsWith(".")) continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (/\.(c|m)?[jt]s$/.test(entry.name)) files.push(full);
    }
  };
  for (const dir of ["features", "test", "tests"]) walk(path.join(root, dir));
  return sha256(files.sort(byCodeUnit).map((f) => `${path.relative(root, f)}\n${fs.readFileSync(f, "utf8")}`).join("\n"));
}

/** The scenario's clock (milliseconds, as a Caller's), sleep (seconds) and jitter. In
 * replay nothing waits: a sleep moves the clock on, as Faulty's slow answers do, and the
 * jitter is half its range. In record mode a sleep waits. */
export class Clock {
  constructor(fake) {
    Object.assign(this, { fake, offset: 0, slept: 0, base: performance.now() });
    this.now = () => (this.fake ? this.base : performance.now()) + this.offset * 1000;
    this.sleep = async (seconds) => {
      this.slept += seconds;
      if (this.fake) this.offset += seconds;
      else await new Promise((resolve) => setTimeout(resolve, seconds * 1000));
    };
    this.advance = (seconds) => {
      this.offset += seconds;
    };
    // A Caller's jitter: from node:crypto, like every random value here.
    this.random = () => (this.fake ? 0.5 : randomInt(2 ** 32) / 2 ** 32);
  }
}

/** One scenario's calls: its cassette, the faults put on it, the clock, the requests
 * made, and the names its test customers gave. */
export class Tape {
  constructor(t, found, scenario, tags, text, { network, customers = {}, steps = "" } = {}) {
    Object.assign(this, { t, settings: found, scenario, text, network, customers, stepsHash: steps });
    this.path = pathFor(scenario, found);
    this.borrowed = null;
    for (const tag of tags) if (tag.startsWith("@cassette:")) this.borrow(tag.slice(10).replace(/^"|"$/g, ""));
    this.clock = new Clock(!found.recording || this.borrowed !== null);
    Object.assign(this, { requests: [], errors: [], names: {}, cassette: null, recorder: null, failed: false });
    this.work = fs.mkdtempSync(path.join(os.tmpdir(), "pubtest-cassette-"));
    this.report = path.join(this.work, "report.jsonl");
    this.faulty = new t.Faulty({ fetch: (url, init) => this.#inner(url, init) }, [], { advance: this.clock.advance });
    this.savedEnv = {};
    if (!found.recording || this.borrowed !== null) this.#replayedNames();
  }

  /** Replay another scenario's cassette: selector names it ("FILE: TITLE", or a TITLE of
   * this feature's), or, as a tag must, its cassette's path without .json. */
  borrow(selector) {
    if (selector.includes("/") && !selector.includes(": ")) this.borrowed = path.join(this.settings.cassettes, `${selector.replace(/\.json$/, "")}.json`);
    else this.borrowed = pathFor(parse(selector, this.scenario.feature), this.settings);
    this.cassette = null;
    if (this.clock) {
      this.clock.fake = true;
      this.#replayedNames();
    }
  }

  /** A fault on the calls to NAME (a plugin, or a prefix of plugins). */
  fault(name, effect, { nth = "*", where = "", body } = {}) {
    const t = this.t;
    class Prefixed extends t.Fault {
      matches(request) {
        return matchesName(name, request.plugin) && super.matches(request);
      }
    }
    this.faulty.rules.push(new Prefixed({ match: `* ${where}`.trim(), nth, effect, ...(body === undefined ? {} : { body }) }));
  }

  /** The names a test customer gave: made by its setup when recording, read back from
   * the cassette in replay. */
  async namesOf(customer) {
    if (!(customer in this.names) && this.settings.recording && this.borrowed === null) {
      const found = this.customers[customer];
      if (!found) throw new Error(`no test customer ${customer}: register(api, { customers: [...] }) names it`);
      this.names[customer] = { ...((await found.setup?.(this)) ?? {}) };
    }
    return (this.names[customer] ??= {});
  }

  /** The transport: the scenario's requests go through it. */
  fetch = async (url, init = {}) => {
    this.requests.push(init.integrations?.plugin ?? null);
    return this.faulty.fetch(url, init);
  };

  async #inner(url, init) {
    if (this.settings.recording && this.borrowed === null) {
      this.recorder ??= new this.t.Recorder(this.network ?? this.t.LIVE, null, { scenario: this.scenario.id, consumer: consumer(this.settings.root), clock: this.clock.now });
      return this.recorder.fetch(url, init);
    }
    return this.#loaded().fetch(url, init);
  }

  #loaded() {
    if (this.cassette === null) {
      const source = this.borrowed ?? this.path;
      if (!fs.existsSync(source)) {
        const whose = this.borrowed === null ? this.scenario.id : path.relative(this.settings.cassettes, source);
        const message = `no cassette for ${whose}: record it (\`pubtest record "${this.scenario.id}"\`)`;
        this.errors.push(message);
        throw new this.t.NoSnapshot(message);
      }
      const cassette = new this.t.Cassette(source, { mode: "replay" });
      const answer = cassette.fetch;
      cassette.fetch = async (url, init) => {
        try {
          return await answer(url, init);
        } catch (err) {
          if (err instanceof this.t.NoSnapshot) this.errors.push(err.message); // kept, so code that swallows it still fails
          throw err;
        }
      };
      this.cassette = cassette;
    }
    return this.cassette;
  }

  #replayedNames() {
    try {
      const data = JSON.parse(fs.readFileSync(this.borrowed ?? this.path, "utf8"));
      this.names = structuredClone(data.current?.recorded?.pubtest?.names ?? {});
    } catch {
      // no cassette: no names
    }
  }

  begin() {
    this.restore = this.t.use(this);
    let env = { [CASSETTE]: this.borrowed ?? this.path, [REPORT]: this.report };
    if (this.settings.recording && this.borrowed === null) {
      // A program records into a file of its own, which the scenario takes as its
      // recording when it makes no calls itself.
      env = { [CASSETTE]: path.join(this.work, "child.json"), [CASSETTES]: fs.realpathSync(this.work), [REPORT]: this.report };
    }
    env.PYTHONPATH = [CHILD, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter);
    env.NODE_OPTIONS = [process.env.NODE_OPTIONS, `--import=${pathToFileURL(path.join(CHILD, "report.mjs")).href}`].filter(Boolean).join(" ");
    for (const [k, v] of Object.entries(env)) {
      this.savedEnv[k] = process.env[k];
      process.env[k] = v;
    }
  }

  children() {
    if (!fs.existsSync(this.report)) return [];
    return fs.readFileSync(this.report, "utf8").split("\n").filter((l) => l.trim()).map((l) => JSON.parse(l));
  }

  /** Close the scenario: undo what begin() did, check or save its cassette, run its
   * customers' cleanups. Returns what fails it. */
  async end() {
    const problems = [];
    const own = this.settings.recording && this.borrowed === null;
    try {
      this.restore?.();
      for (const [k, v] of Object.entries(this.savedEnv)) {
        if (v === undefined) delete process.env[k];
        else process.env[k] = v;
      }
      if (own) {
        if (!this.failed) problems.push(...this.#save());
      } else problems.push(...this.#check());
      if (process.env[PLAN]) this.#plan(problems);
    } finally {
      if (own) {
        for (const [name, customer] of Object.entries(this.customers)) {
          if (!(name in this.names) || !customer.cleanup) continue;
          try {
            await customer.cleanup(this, this.names[name]);
          } catch (err) {
            problems.push(`the test customer ${name}'s cleanup failed: ${err?.message ?? err}`);
          }
        }
      }
      fs.rmSync(this.work, { recursive: true, force: true });
    }
    return problems;
  }

  #check() {
    const problems = this.failed ? [] : [...new Set(this.errors)];
    const children = this.children();
    const missed = children.reduce((n, c) => n + Math.max(0, (c.sent ?? 0) - (c.answered ?? 0)), 0);
    if (missed && !this.failed) problems.push(`${missed} call${missed !== 1 ? "s" : ""} a program made had no recording in ${this.scenario.id}: record it (\`pubtest record "${this.scenario.id}"\`)`);
    if (this.borrowed !== null || this.failed || !fs.existsSync(this.path)) return problems;
    const cassette = this.cassette ?? new this.t.Cassette(this.path, { mode: "replay" });
    const used = new Set(cassette.calls.flatMap((c, i) => (c.used ? [i] : [])));
    // A program names the cassette it replayed as begin() gave it, in
    // INTEGRATIONS_CASSETTE: compared as text, a path read from its report is
    // never looked up on disk.
    for (const child of children) {
      if (child.cassette === this.path) for (const i of child.used ?? []) used.add(i);
    }
    const left = cassette.calls.flatMap((c, i) => (used.has(i) ? [] : [c]));
    if (left.length) {
      problems.push([`${left.length} recorded call${left.length !== 1 ? "s" : ""} in ${this.scenario.id} never made:`,
        ...left.map((c) => `  ${c.plugin ?? "*"} ${c.operation ?? "*"} ${c.request.method.toUpperCase()} ${c.request.url}`),
        `record it: pubtest record "${this.scenario.id}"`].join("\n"));
    }
    return problems;
  }

  #stamp(current) {
    current.recorded ??= {};
    current.recorded.integrations = integrationsVersion(this.settings.root);
    current.recorded.consumer ||= consumer(this.settings.root);
    current.recorded.pubtest = { scenario: this.text, steps: this.stepsHash, names: this.names };
    return current;
  }

  #save() {
    const own = this.recorder?.calls ?? [];
    const childFile = path.join(this.work, "child.json");
    const child = fs.existsSync(childFile) ? JSON.parse(fs.readFileSync(childFile, "utf8")) : null;
    if (own.length && child) return [`${this.scenario.id} made calls itself and through a program it ran: a cassette holds one process's calls, so record them in separate scenarios`];
    let current;
    try {
      current = own.length ? this.recorder.recording() : child?.current;
    } catch (err) {
      return [err.message];
    }
    if (!current?.calls?.length) {
      fs.rmSync(this.path, { force: true }); // it makes no calls now: its old cassette goes
      return [];
    }
    let old = {};
    if (fs.existsSync(this.path)) old = JSON.parse(fs.readFileSync(this.path, "utf8"));
    const baseline = old.format === this.t.FORMAT ? (old.baseline ?? old.current ?? null) : null;
    this.t.writeCassette(this.path, { format: this.t.FORMAT, scenario: this.scenario.id, current: this.#stamp(current), baseline }, this.settings.cassettes);
    return [];
  }

  #plan(problems) {
    let reason = null;
    if (this.borrowed === null) {
      if (this.errors.some((e) => e.startsWith("no cassette for"))) reason = "it has no cassette";
      else if (problems.length) reason = "it no longer fits its cassette";
      else if (fs.existsSync(this.path)) {
        const recorded = JSON.parse(fs.readFileSync(this.path, "utf8")).current?.recorded ?? {};
        const stamp = recorded.pubtest ?? {};
        const version = integrationsVersion(this.settings.root);
        if (stamp.scenario !== this.text) reason = "its text changed";
        else if (stamp.steps !== this.stepsHash) reason = "its steps' code changed";
        else if (recorded.integrations !== version) reason = `integrations is ${version}, not ${recorded.integrations}`;
      }
    }
    fs.appendFileSync(process.env[PLAN], `${JSON.stringify({ scenario: this.scenario.id, changed: reason })}\n`);
  }
}

/** The options a suite's own Caller takes, so the scenario's clock is its clock:
 * new Caller(repo, app, { ...callerOptions(ctx) }). integrations gives no default to
 * set, so a Caller made without them waits as it always does. */
export function callerOptions(ctx) {
  const clock = ctx?.tape?.clock;
  return clock ? { clock: clock.now, sleep: clock.sleep, random: clock.random } : {};
}

// --- the scenario, as each runner tells it ----------------------------------------

function rows(table) {
  return (table?.rows ?? []).map((r) => r.cells.map((c) => c.value));
}

/** A pickle's scenario, steps and tags, from cucumber's pickle and gherkin document. */
export function fromPickle(pickle, document) {
  const feature = path.basename(pickle.uri);
  const [scenarioId, rowId] = pickle.astNodeIds;
  let title = pickle.name;
  let row = null;
  const children = (document?.feature?.children ?? []).flatMap((c) => (c.rule ? c.rule.children : [c]));
  for (const child of children) {
    if (child.scenario?.id !== scenarioId) continue;
    title = child.scenario.name;
    if (rowId) {
      const body = child.scenario.examples.flatMap((e) => e.tableBody);
      const at = body.findIndex((r) => r.id === rowId);
      if (at >= 0) row = at + 1;
    }
  }
  const steps = pickle.steps.map((s) => [s.text, s.argument?.docString?.content ?? null, s.argument?.dataTable ? rows(s.argument.dataTable) : null]);
  return { scenario: new Scenario(feature, title, row), steps, tags: pickle.tags.map((t) => t.name) };
}

/** The same for quickpickle, which gives the scenario's rendered name and steps: the
 * feature file is compiled with @cucumber/gherkin, quickpickle's own parser. */
export async function fromQuickpickle(world) {
  const file = world.context?.task?.file?.filepath;
  if (!file) return null;
  const gherkin = await import("@cucumber/gherkin");
  const messages = await import("@cucumber/messages");
  const builder = new gherkin.AstBuilder(messages.IdGenerator.uuid());
  const matcher = new gherkin.GherkinClassicTokenMatcher();
  const document = new gherkin.Parser(builder, matcher).parse(fs.readFileSync(file, "utf8"));
  const pickles = gherkin.compile(document, file, messages.IdGenerator.uuid());
  const wanted = world.info.steps ?? [];
  const pickle = pickles.find((p) => p.name === world.info.scenario && JSON.stringify(p.steps.map((s) => s.text)) === JSON.stringify(wanted))
    ?? pickles.find((p) => p.name === world.info.scenario);
  return pickle ? fromPickle(pickle, document) : null;
}
