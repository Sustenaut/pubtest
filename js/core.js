// What every step shares: a scenario's context, what its action came to,
// and how a step's quoted value is compared (GRAMMAR.md).
import fs from "node:fs";
import path from "node:path";

/** What an action raised. */
export class Refused {
  constructor(error) {
    this.error = error;
  }
  get message() {
    return this.error instanceof ExitError ? "" : String(this.error?.message ?? this.error);
  }
}

/** process.exit(code), caught: a refusal with its exit code. */
export class ExitError extends Error {
  constructor(code) {
    super(`exited with ${code}`);
    this.code = code ?? 0;
  }
}

/** What a scenario's action came to, whichever kind of When it was. */
export class Result {
  constructor(fields = {}) {
    Object.assign(this, { value: undefined, refused: null, code: 0, stdout: "", stderr: "", argv: [] }, fields);
  }
  describe() {
    const head = this.argv.length ? `$ ${this.argv.join(" ")}\n` : "";
    const refused = this.refused ? `refused: ${JSON.stringify(this.refused.message)}\n` : "";
    return `${head}exit ${this.code}\n${refused}stdout: ${JSON.stringify(this.stdout)}\nstderr: ${JSON.stringify(this.stderr)}`;
  }
}

export function filesIn(root) {
  const out = {};
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.isFile()) out[path.relative(root, full).split(path.sep).join("/")] = fs.readFileSync(full).toString("base64");
    }
  };
  if (fs.existsSync(root)) walk(root);
  return out;
}

/** A scenario's state, and the cleanups that run when it ends, in reverse. */
export class Context {
  constructor() {
    this.outcome = null;
    this.refusalRead = false;
    this.directory = null;
    this.secrets = [];
    this.written = null;
    this.headers = {};
    this.programs = {};
    this.fakes = {};
    this.recorded = [];
    this.standins = null;
    this.answer = null;
    this.cleanups = [];
  }
  get result() {
    return this.outcome?.value;
  }
  get refused() {
    return this.outcome?.refused ?? null;
  }
  cleanup(fn) {
    this.cleanups.push(fn);
    return fn;
  }
  /** Before an action: the scratch directory as it was before the first one. */
  acting() {
    if (this.directory && this.written === null) this.written = filesIn(this.directory);
  }
  /** Do the scenario's action: keep what it returns, or what it raises, and
   * what it printed (process.stdout, process.stderr and console); a
   * process.exit is a refusal with its code. */
  async attempt(action) {
    this.acting();
    const outcome = new Result();
    const saved = { out: process.stdout.write, err: process.stderr.write, exit: process.exit };
    const consoleSaved = { log: console.log, info: console.info, warn: console.warn, error: console.error };
    let out = "";
    let err = "";
    process.stdout.write = (chunk) => ((out += String(chunk)), true);
    process.stderr.write = (chunk) => ((err += String(chunk)), true);
    console.log = console.info = (...a) => (out += a.join(" ") + "\n");
    console.warn = console.error = (...a) => (err += a.join(" ") + "\n");
    process.exit = (code) => {
      throw new ExitError(code);
    };
    try {
      outcome.value = await action();
    } catch (error) {
      if (error instanceof ExitError) {
        outcome.code = error.code;
        if (error.code !== 0) outcome.refused = new Refused(error);
      } else {
        outcome.refused = new Refused(error);
        outcome.code = 1;
      }
    } finally {
      Object.assign(process.stdout, { write: saved.out });
      Object.assign(process.stderr, { write: saved.err });
      process.exit = saved.exit;
      Object.assign(console, consoleSaved);
    }
    outcome.stdout = out;
    outcome.stderr = err;
    this.outcome = outcome;
    this.refusalRead = false;
    return outcome.value;
  }
  ran(outcome) {
    this.outcome = outcome;
    this.refusalRead = false;
    return outcome;
  }
  async close() {
    let first = null;
    while (this.cleanups.length) {
      try {
        await this.cleanups.pop()();
      } catch (e) {
        first ??= e;
      }
    }
    if (first) throw first;
  }
}

/** A step's quoted value: compared as text with a text result; otherwise
 * read as JSON, and as text when it does not read as JSON. */
export function same(actual, wanted) {
  if (Buffer.isBuffer(actual)) actual = actual.toString("utf8");
  if (typeof actual === "string") return actual === wanted;
  let want;
  try {
    want = JSON.parse(wanted);
  } catch {
    return String(actual) === wanted;
  }
  if ((typeof actual === "boolean") !== (typeof want === "boolean")) return false; // true is not 1
  return deepEqual(actual, want);
}

export function deepEqual(a, b) {
  return JSON.stringify(normal(a)) === JSON.stringify(normal(b));
}

function normal(v) {
  if (Array.isArray(v)) return v.map(normal);
  if (v && typeof v === "object") return Object.fromEntries(Object.keys(v).sort().map((k) => [k, normal(v[k])]));
  return v === undefined ? null : v;
}

/** The value at a dotted key: a.b.0 is data.a.b[0]. */
export function dig(data, key) {
  for (const part of key.split(".")) data = Array.isArray(data) ? data[Number(part)] : data?.[part];
  return data;
}

/** Text contains it, a list holds it, a map has it as a key. */
export function includes(container, item) {
  if (Buffer.isBuffer(container)) container = container.toString("utf8");
  if (typeof container === "string") return container.includes(item);
  let want = item;
  try {
    want = JSON.parse(item);
  } catch {
    // compared as text
  }
  if (Array.isArray(container)) return container.some((x) => deepEqual(x, want) || String(x) === item);
  if (container && typeof container === "object") return item in container;
  return false;
}

export function isEmpty(v) {
  return v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0) ||
    (typeof v === "object" && !Array.isArray(v) && Object.keys(v).length === 0);
}

export function show(v) {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

/** Split a command as a POSIX shell splits words: quotes and backslashes. */
export function split(command) {
  const words = [];
  let word = null;
  let quote = null;
  for (let i = 0; i < command.length; i++) {
    const c = command[i];
    if (quote === "'") {
      if (c === "'") quote = null;
      else word += c;
    } else if (quote === '"') {
      if (c === '"') quote = null;
      else if (c === "\\" && i + 1 < command.length && '"\\$`'.includes(command[i + 1])) word += command[++i];
      else word += c;
    } else if (c === "'" || c === '"') {
      quote = c;
      word ??= "";
    } else if (c === "\\" && i + 1 < command.length) {
      word = (word ?? "") + command[++i];
    } else if (/\s/.test(c)) {
      if (word !== null) words.push(word);
      word = null;
    } else {
      word = (word ?? "") + c;
    }
  }
  if (quote) throw new Error(`an unclosed ${quote} in ${command}`);
  if (word !== null) words.push(word);
  return words;
}

export function binVar(name) {
  return name.replace(/[^A-Za-z0-9]/g, "_").toUpperCase() + "_BIN_DIR";
}
