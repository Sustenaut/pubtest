// pubtest's steps for Node (GRAMMAR.md): register(api) defines them with a
// runner's Given/When/Then/Before/After, cucumber-js's or quickpickle's.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { binVar, Context, deepEqual, dig, filesIn, includes, isEmpty, matches, repository, Result, same, show, split, yamlDocuments } from "./core.js";
import { fromPickle, fromQuickpickle, matchesName, NEVER, selected, settings, standInOnly, startSession, supportHash, Tape, textHash, transports } from "./cassettes.js";

const BASIC = ["sh", "bash", "env", "cat", "echo", "printf", "mkdir", "rm", "cp", "mv", "chmod", "ls", "sed",
  "grep", "head", "tail", "tr", "cut", "sort", "uniq", "wc", "dirname", "basename", "mktemp", "date",
  "sleep", "true", "false", "test", "touch", "readlink", "realpath", "id", "uname"];

function fail(message) {
  throw new Error(message);
}

function check(ok, message) {
  if (!ok) fail(typeof message === "function" ? message() : message);
}

function at(ctx, p) {
  return path.join(ctx.directory ?? process.cwd(), p);
}

/** The scenario's tape: its cassette, faults and calls (cassettes.js). */
function tape(ctx) {
  check(ctx.tape, 'the integration steps need the record/replay harness: install @sustenaut/integrations and set "pubtest": {"cassettes": ...} in pubrules.json (GRAMMAR.md, "Record and replay")');
  return ctx.tape;
}

function returned(ctx) {
  check(ctx.outcome, "no action was taken: a When leaves the result");
  if (ctx.refused) {
    ctx.refusalRead = true;
    fail(`it was refused: ${JSON.stringify(ctx.refused.message || ctx.outcome.stderr)}`);
  }
  return ctx.result;
}

/** The refusal, read: a step that reads it marks it so. */
function refusal(ctx) {
  ctx.refusalRead = true;
  check(ctx.refused, () => `it was not refused: the result is ${show(ctx.result)}`);
  return ctx.refused;
}

/** The value at a dotted key, failing clearly when it is not there. */
function at_(data, key, what) {
  let here = data;
  for (const part of key.split(".")) {
    if (here === null || here === undefined || !(part in Object(here))) {
      fail(`${what} has no ${key}: ${show(data)}`);
    }
    here = Array.isArray(here) ? here[Number(part)] : here[part];
  }
  return here;
}

/** A text's lines, as Python's splitlines gives them: no last empty one. */
function lines(text) {
  const all = (text ?? "").split(/\r\n|\n|\r/);
  if (all.at(-1) === "") all.pop();
  return all;
}

function rows(table) {
  return typeof table?.raw === "function" ? table.raw() : table?.data ?? table;
}

function setEnv(ctx, name, value) {
  if (!ctx.envSaved) {
    ctx.envSaved = {};
    ctx.cleanup(() => {
      for (const [k, v] of Object.entries(ctx.envSaved)) {
        if (v === undefined) delete process.env[k];
        else process.env[k] = v;
      }
    });
  }
  if (!(name in ctx.envSaved)) ctx.envSaved[name] = process.env[name];
  if (value === undefined) delete process.env[name];
  else process.env[name] = value;
}

// --- stand-ins ----------------------------------------------------------------

class Standins {
  constructor(root) {
    this.bin = path.join(root, "standins");
    this.basic = path.join(root, "basic");
    this.log = path.join(root, "standins.log");
    fs.mkdirSync(this.bin, { recursive: true });
    fs.writeFileSync(this.log, "");
    this.only = false;
    this.base = process.env.PATH ?? "";
  }
  script(name, body) {
    const file = path.join(this.bin, name);
    fs.writeFileSync(file, `#!${process.execPath}
const fs = require("node:fs");
fs.appendFileSync(${JSON.stringify(this.log)}, JSON.stringify({ name: ${JSON.stringify(name)}, args: process.argv.slice(2) }) + "\\n");
${body}
`);
    fs.chmodSync(file, 0o755);
  }
  add(name, out = "", err = "", code = 0) {
    this.script(name, `process.stdout.write(${JSON.stringify(out)}); process.stderr.write(${JSON.stringify(err)}); process.exitCode = ${code};`);
  }
  addReader(name) {
    this.script(name, `fs.appendFileSync(${JSON.stringify(this.log)}, JSON.stringify({ name: ${JSON.stringify(name)}, input: fs.readFileSync(0, "utf8") }) + "\\n");`);
  }
  addTurns(name, answers) {
    const store = path.join(this.bin, "..", `${name}.answers.json`);
    fs.writeFileSync(store, JSON.stringify(answers));
    this.script(name, `const answers = JSON.parse(fs.readFileSync(${JSON.stringify(store)}, "utf8"));
const args = process.argv.slice(2).join(" ");
const matches = (p) => new RegExp("^" + p.split("*").map((s) => s.replace(/[.+?^\${}()|[\\]\\\\]/g, "\\\\$&")).join(".*") + "$").test(args);
const matching = answers.filter((a) => matches(a.args));
const fresh = matching.filter((a) => !a.given);
const answer = fresh[0] ?? matching.at(-1) ?? { exit: 127, stderr: ${JSON.stringify(name)} + ": no answer for " + args + "\\n" };
answer.given = true;
fs.writeFileSync(${JSON.stringify(store)}, JSON.stringify(answers));
process.stdout.write(answer.stdout ?? ""); process.stderr.write(answer.stderr ?? ""); process.exitCode = Number(answer.exit ?? 0);`);
  }
  remove(name) {
    fs.rmSync(path.join(this.bin, name), { force: true });
  }
  path() {
    if (!this.only) return `${this.bin}${path.delimiter}${this.base}`;
    fs.mkdirSync(this.basic, { recursive: true });
    for (const tool of BASIC) {
      const found = this.base.split(path.delimiter).map((d) => path.join(d, tool)).find((p) => fs.existsSync(p));
      const link = path.join(this.basic, tool);
      if (found && !fs.existsSync(link) && !fs.existsSync(path.join(this.bin, tool))) fs.symlinkSync(found, link);
    }
    return `${this.bin}${path.delimiter}${this.basic}`;
  }
  entries(name) {
    return fs.readFileSync(this.log, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l))
      .filter((e) => name === undefined || e.name === name);
  }
  runs(name) {
    return this.entries(name).filter((e) => e.args).map((e) => e.args);
  }
  inputs(name) {
    return this.entries(name).filter((e) => typeof e.input === "string").map((e) => e.input);
  }
}

/** The scenario's own directory for what pubtest keeps outside the scratch
 * directory (stand-ins, bare remotes), removed when the scenario ends, as
 * pytest's tmp_path is. */
function scenarioTemp(ctx) {
  if (!ctx.temp) {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "pubtest-"));
    ctx.temp = dir;
    ctx.cleanup(() => fs.rmSync(dir, { recursive: true, force: true }));
  }
  return ctx.temp;
}

function standins(ctx) {
  if (!ctx.standins) {
    ctx.standins = new Standins(path.join(scenarioTemp(ctx), "pubtest"));
    setEnv(ctx, "PATH", ctx.standins.path());
  }
  return ctx.standins;
}

function refreshPath(ctx) {
  process.env.PATH = ctx.standins.path();
}

// --- fake services ------------------------------------------------------------

class Fake {
  constructor(name) {
    this.name = name;
    this.answers = {};
    this.requests = [];
    this.server = http.createServer((req, res) => {
      let body = "";
      req.on("data", (c) => (body += c));
      req.on("end", () => {
        this.requests.push({ method: req.method, path: req.url, body, headers: req.headers });
        const queue = this.answers[`${req.method} ${req.url}`] ?? this.answers[`${req.method} ${req.url.split("?")[0]}`];
        const [status, text, extra] = queue ? (queue.length > 1 ? queue.shift() : queue[0]) : [404, "", {}];
        const headers = { "content-length": Buffer.byteLength(text) };
        if (/^\s*[{[]/.test(text)) headers["content-type"] = "application/json";
        for (const [k, v] of Object.entries(extra ?? {})) headers[k.toLowerCase()] = v;
        res.writeHead(status, headers);
        res.end(text);
      });
    });
  }
  start() {
    return new Promise((resolve) => this.server.listen(0, "127.0.0.1", resolve));
  }
  get url() {
    return `http://127.0.0.1:${this.server.address().port}`;
  }
  answer(request, status, body = "", headers = {}) {
    (this.answers[request] ??= []).push([status, body, headers]);
  }
  stop() {
    return new Promise((resolve) => this.server.close(() => resolve()));
  }
}

async function fake(ctx, name) {
  if (!ctx.fakes[name]) {
    const f = new Fake(name);
    await f.start();
    ctx.fakes[name] = f;
    setEnv(ctx, name.replace(/[^A-Za-z0-9]/g, "_").toUpperCase() + "_URL", f.url);
    ctx.cleanup(() => f.stop());
  }
  return ctx.fakes[name];
}

function asked(ctx, name) {
  check(ctx.fakes[name], `there is no fake ${name} service`);
  return ctx.fakes[name].requests;
}

/** The requests `name` was asked that are `request`, "METHOD PATH", its
 * query left out unless `request` names one. */
function requests(ctx, name, request) {
  return asked(ctx, name).filter((q) => [`${q.method} ${q.path}`, `${q.method} ${q.path.split("?")[0]}`].includes(request));
}

function printedJson(ctx) {
  try {
    return JSON.parse(ctx.outcome?.stdout ?? "");
  } catch {
    return fail(`it printed no JSON\n${showRun(ctx.outcome)}`);
  }
}

function names(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).map((e) => e.name + (e.isDirectory() ? "/" : "")).sort();
}

/** Everything the action produced, by where it went. */
export function produced(ctx) {
  const out = {};
  const o = ctx.outcome;
  if (o) {
    out.stdout = o.stdout;
    out.stderr = o.stderr;
    out["the result"] = o.value === undefined ? "" : (typeof o.value === "string" ? o.value : show(o.value));
    if (o.refused) out["the refusal"] = `${o.refused.message} ${o.refused.error?.stack ?? ""}`;
  }
  if (ctx.answer) out["the answer"] = JSON.stringify(ctx.answer.headers) + ctx.answer.text;
  if (ctx.directory) {
    const before = ctx.written ?? {};
    for (const [p, data] of Object.entries(filesIn(ctx.directory))) {
      if (before[p] !== data) out[`the file ${p}`] = Buffer.from(data, "base64").toString("utf8");
    }
  }
  // The arguments it gave a program; what it gave one through its environment is deliberately not a leak.
  if (ctx.standins) out["the programs it ran"] = JSON.stringify(ctx.standins.runs());
  for (const [name, f] of Object.entries(ctx.fakes)) out[`what it sent ${name}`] = JSON.stringify(f.requests);
  return out;
}

function git(ctx, ...args) {
  return gitIn(ctx.directory ?? process.cwd(), ...args);
}

function gitIn(cwd, ...args) {
  const done = spawnSync("git", args, {
    cwd, encoding: "utf8",
    env: { ...process.env, GIT_AUTHOR_NAME: "pubtest", GIT_AUTHOR_EMAIL: "pubtest@example.org",
      GIT_COMMITTER_NAME: "pubtest", GIT_COMMITTER_EMAIL: "pubtest@example.org" },
  });
  check(done.status === 0, () => `git ${args.join(" ")}: ${done.stderr}`);
  return done.stdout.trim();
}

function runCommand(ctx, command, input) {
  const argv = split(command);
  argv[0] = ctx.programs[argv[0]] ?? argv[0];
  ctx.acting();
  const done = spawnSync(argv[0], argv.slice(1), {
    cwd: ctx.directory ?? process.cwd(), input: input ?? "", encoding: "utf8", timeout: 120_000,
    env: { ...process.env, ...(ctx.standins ? { PATH: ctx.standins.path() } : {}) },
  });
  if (done.error) {
    return ctx.ran(new Result({ code: 127, stderr: String(done.error.message), argv }));
  }
  return ctx.ran(new Result({ code: done.status ?? 1, stdout: done.stdout, stderr: done.stderr, argv }));
}

async function send(ctx, method, p, body, type) {
  check(ctx.client, "the HTTP steps need the suite's client: register(api, { client })");
  const headers = { ...ctx.headers, ...(type ? { "content-type": type } : {}) };
  ctx.acting();
  ctx.answer = await ctx.client(method, p, headers, body);
  ctx.ran(new Result({ value: ctx.answer }));
}

function answer(ctx) {
  check(ctx.answer, "no request was sent");
  return ctx.answer;
}

function showAnswer(a) {
  return `${a.status} ${JSON.stringify(a.headers)}\n${a.text.slice(0, 2000)}`;
}

function showRun(r) {
  return r?.describe ? r.describe() : show(r);
}

/** The steps, as [kind, expression, step(ctx, ...args)]. */
export const STEPS = [
  // The result
  ["Then", "the result is {string}", (ctx, v) => { const got = returned(ctx); check(same(got, v), () => `the result is ${show(got)}, not ${v}`); }],
  ["Then", "the result is not {string}", (ctx, v) => { const got = returned(ctx); check(!same(got, v), () => `the result is ${v}`); }],
  ["Then", "the result is:", (ctx, doc) => {
    const got = returned(ctx);
    const table = rows(doc);
    if (Array.isArray(table)) {
      const [keys, ...data] = table;
      check(Array.isArray(got) && got.length === data.length, () => `the result is ${show(got)}`);
      data.forEach((row, i) => keys.forEach((k, j) => check(same(dig(got[i], k), row[j]), () => `the result is ${show(got)}; ${k} is not ${row[j]}`)));
      return;
    }
    check(same(got, String(doc)), () => `the result is ${show(got)}, not:\n${doc}`);
  }],
  ["Then", "the result includes {string}", (ctx, v) => { const got = returned(ctx); check(includes(got, v), () => `the result ${show(got)} does not include ${v}`); }],
  ["Then", "the result does not include {string}", (ctx, v) => { const got = returned(ctx); check(!includes(got, v), () => `the result ${show(got)} includes ${v}`); }],
  ["Then", "the result's {string} is {string}", (ctx, k, v) => { const got = dig(returned(ctx), k); check(same(got, v), () => `the result's ${k} is ${show(got)}, not ${v}`); }],
  ["Then", "the result has {int} {word}", (ctx, n, noun) => { const got = returned(ctx); check(got?.length === n, () => `the result has ${got?.length} ${noun}, not ${n}: ${show(got)}`); }],
  ["Then", "the result is empty", (ctx) => { const got = returned(ctx); check(isEmpty(got), () => `the result is ${show(got)}`); }],
  ["Then", "it is refused, saying {string}", (ctx, t) => {
    ctx.refusalRead = true;
    check(ctx.refused, () => `it was not refused: the result is ${show(ctx.result)}`);
    const said = ctx.refused.message || ctx.outcome.stderr;
    check(said.includes(t), () => `it was refused, saying ${JSON.stringify(said)}`);
  }],
  ["Then", "it is refused", (ctx) => { ctx.refusalRead = true; check(ctx.refused, () => `it was not refused: the result is ${show(ctx.result)}`); }],
  ["Then", "the result matches {string}", (ctx, p) => {
    const got = returned(ctx);
    check(typeof got === "string", () => `the result is ${show(got)}, not text`);
    check(matches(p, got), () => `the result ${JSON.stringify(got)} does not match ${JSON.stringify(p)}`);
  }],
  ["Then", "it is not refused", (ctx) => { ctx.refusalRead = true; check(!ctx.refused, () => `it was refused, saying ${ctx.refused.message}`); }],
  ["Then", "the result's {string} includes {string}", (ctx, k, v) => { const got = at_(returned(ctx), k, "the result"); check(includes(got, v), () => `the result's ${k} ${show(got)} does not include ${v}`); }],
  ["Then", "the result's {string} matches {string}", (ctx, k, p) => {
    const got = at_(returned(ctx), k, "the result");
    check(typeof got === "string", () => `the result's ${k} is ${show(got)}, not text`);
    check(matches(p, got), () => `the result's ${k} ${JSON.stringify(got)} does not match ${JSON.stringify(p)}`);
  }],
  ["Then", "the refusal is a {string}", (ctx, name) => {
    const error = refusal(ctx).error;
    const classes = [];
    for (let p = error === null || error === undefined ? null : Object.getPrototypeOf(Object(error)); p; p = Object.getPrototypeOf(p)) {
      if (p.constructor?.name) classes.push(p.constructor.name);
    }
    check(classes.includes(name), () => `the refusal is a ${classes.join(" < ")}, not a ${name}`);
  }],
  ["Then", "the refusal's {string} is {string}", (ctx, k, v) => {
    const r = refusal(ctx);
    const got = k === "message" ? r.message : at_(r.error, k, "the refusal");
    check(same(got, v), () => `the refusal's ${k} is ${show(got)}, not ${v}`);
  }],

  // Files
  ["Given", "a scratch directory", (ctx) => {
    ctx.directory = fs.mkdtempSync(path.join(os.tmpdir(), "pubtest-scratch-"));
    const dir = ctx.directory;
    ctx.cleanup(() => fs.rmSync(dir, { recursive: true, force: true }));
  }],
  ["Given", "a file {string} holding {string}", (ctx, p, t) => write(ctx, p, `${t}\n`)],
  ["Given", "a file {string} holding:", (ctx, p, doc) => write(ctx, p, `${doc}\n`)],
  ["Given", "a file {string} copied from {string}", (ctx, p, src) => {
    const origin = path.resolve(ctx.repository, src);
    const inside = path.relative(path.resolve(ctx.repository), origin);
    check(!path.isAbsolute(src) && inside !== ".." && !inside.startsWith(`..${path.sep}`) && !path.isAbsolute(inside),
      `${src} is not in the repository: copy only the repository's own files`);
    check(fs.existsSync(origin), `the repository has no ${src}`);
    const target = at(ctx, p);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.cpSync(origin, target, { recursive: true });
  }],
  ["Given", "the file {string} is executable", (ctx, p) => fs.chmodSync(at(ctx, p), 0o755)],
  ["Given", "the file {string} is removed", (ctx, p) => fs.rmSync(at(ctx, p), { recursive: true, force: true })],
  ["When", "the file {string} changes to:", (ctx, p, doc) => write(ctx, p, `${doc}\n`)],
  ["Then", "the file {string} exists", (ctx, p) => check(fs.existsSync(at(ctx, p)), `there is no ${p}`)],
  ["Then", "the file {string} does not exist", (ctx, p) => check(!fs.existsSync(at(ctx, p)), `${p} exists`)],
  ["Then", "the file {string} holds {string}", (ctx, p, t) => { const got = text(ctx, p); check(got.replace(/\n$/, "") === t, `${p} holds ${JSON.stringify(got)}`); }],
  ["Then", "the file {string} holds:", (ctx, p, doc) => { const got = text(ctx, p); check(got.replace(/\n$/, "") === String(doc).replace(/\n$/, ""), `${p} holds:\n${got}`); }],
  ["Then", "the file {string} includes {string} once", (ctx, p, t) => { const n = text(ctx, p).split("\n").filter((l) => l.includes(t)).length; check(n === 1, `${p} has ${n} lines with ${JSON.stringify(t)}`); }],
  ["Then", "the file {string} includes {string}", (ctx, p, t) => check(text(ctx, p).includes(t), `${p} does not include ${JSON.stringify(t)}`)],
  ["Then", "the file {string} does not include {string}", (ctx, p, t) => check(!text(ctx, p).includes(t), `${p} includes ${JSON.stringify(t)}`)],
  ["Then", "the JSON in {string} is:", (ctx, p, doc) => { const got = JSON.parse(text(ctx, p)); check(same(got, String(doc)), `${p} holds ${show(got)}`); }],
  ["Then", "the JSON in {string} has {string} equal to {string}", (ctx, p, k, v) => { const got = dig(JSON.parse(text(ctx, p)), k); check(same(got, v), `${p}'s ${k} is ${show(got)}, not ${v}`); }],
  ["Then", "the file {string} can be run", (ctx, p) => {
    check(fs.existsSync(at(ctx, p)), `there is no ${p}`);
    let ok = true;
    try { fs.accessSync(at(ctx, p), fs.constants.X_OK); } catch { ok = false; }
    check(ok, `${p} is not executable`);
  }],
  ["Then", "the directory {string} holds:", (ctx, p, doc) => {
    const dir = at(ctx, p);
    check(fs.existsSync(dir) && fs.statSync(dir).isDirectory(), `there is no directory ${p}`);
    const got = names(dir);
    const want = String(doc).split("\n").map((l) => l.trim()).filter(Boolean);
    check(JSON.stringify(got) === JSON.stringify(want), `${p} holds:\n${got.join("\n")}`);
  }],
  ["Then", "the YAML in {string} is:", async (ctx, p, doc) => { const got = await yamlDocuments(text(ctx, p)); check(deepEqual(got, await yamlDocuments(String(doc))), `${p} holds ${show(got)}`); }],
  ["Then", "the YAML in {string} has {string} equal to {string}", async (ctx, p, k, v) => { const got = dig(await yamlDocuments(text(ctx, p)), k); check(same(got, v), `${p}'s ${k} is ${show(got)}, not ${v}`); }],
  ["Then", "nothing was written", (ctx) => {
    check(ctx.directory, "nothing was written needs a scratch directory");
    check(ctx.written !== null, "nothing was written needs a When: it compares with the directory before it");
    const after = filesIn(ctx.directory);
    const changed = [...new Set([...Object.keys(ctx.written), ...Object.keys(after)])].filter((p) => ctx.written[p] !== after[p]).sort();
    check(changed.length === 0, `written: ${changed.join(", ")}`);
  }],

  // The environment
  ["Given", "the environment sets {string} to {string}", (ctx, n, v) => setEnv(ctx, n, v)],
  ["Given", "the environment does not set {string}", (ctx, n) => setEnv(ctx, n, undefined)],

  // Programs
  ["Given", "the program under test is {string}", (ctx, name) => {
    const v = binVar(name);
    check(process.env[v], `${v} is not set: it must name the directory holding ${name}`);
    const p = path.join(process.env[v], name + (process.platform === "win32" ? ".exe" : ""));
    check(fs.existsSync(p), `${v}=${process.env[v]} has no ${name}`);
    ctx.programs[name] = p;
  }],
  ["When", "I run {string}", (ctx, c) => { runCommand(ctx, c); }],
  ["When", "I run {string} with the input:", (ctx, c, doc) => { runCommand(ctx, c, `${doc}\n`); }],
  ["Then", "it succeeds", (ctx) => { ctx.refusalRead = true; check(ctx.outcome?.code === 0, () => showRun(ctx.outcome)); }],
  ["Then", "it fails", (ctx) => { ctx.refusalRead = true; check(ctx.outcome && ctx.outcome.code !== 0, () => showRun(ctx.outcome)); }],
  ["Then", "the exit code is {int}", (ctx, n) => { ctx.refusalRead = true; check(ctx.outcome?.code === n, () => showRun(ctx.outcome)); }],
  ["Then", "it prints {string}", (ctx, t) => check(ctx.outcome?.stdout.includes(t), () => showRun(ctx.outcome))],
  ["Then", "it does not print {string}", (ctx, t) => check(!ctx.outcome?.stdout.includes(t), () => showRun(ctx.outcome))],
  ["Then", "it prints:", (ctx, doc) => check(ctx.outcome?.stdout.replace(/\n$/, "") === String(doc).replace(/\n$/, ""), () => showRun(ctx.outcome))],
  ["Then", "stdout is empty", (ctx) => check(ctx.outcome?.stdout === "", () => showRun(ctx.outcome))],
  ["Then", "stderr is empty", (ctx) => check(ctx.outcome?.stderr === "", () => showRun(ctx.outcome))],
  ["Then", "stderr mentions {string}", (ctx, t) => check(ctx.outcome?.stderr.includes(t), () => showRun(ctx.outcome))],
  ["Then", "stderr does not mention {string}", (ctx, t) => check(!ctx.outcome?.stderr.includes(t), () => showRun(ctx.outcome))],
  ["Then", "it prints the JSON:", (ctx, doc) => { const got = printedJson(ctx); check(same(got, String(doc)), () => `it printed ${show(got)}, not:\n${doc}`); }],
  ["Then", "the JSON it prints has {string} equal to {string}", (ctx, k, v) => { const got = dig(printedJson(ctx), k); check(same(got, v), () => `the ${k} it printed is ${show(got)}, not ${v}`); }],
  ["Then", "it prints a line matching {string}", (ctx, p) => check(lines(ctx.outcome?.stdout).some((l) => matches(p, l)), () => `no line matches ${JSON.stringify(p)}\n${showRun(ctx.outcome)}`)],
  ["Then", "stderr has a line matching {string}", (ctx, p) => check(lines(ctx.outcome?.stderr).some((l) => matches(p, l)), () => `no line of stderr matches ${JSON.stringify(p)}\n${showRun(ctx.outcome)}`)],
  ["Then", "it prints no line matching {string}", (ctx, p) => {
    const found = lines(ctx.outcome?.stdout).filter((l) => matches(p, l));
    check(found.length === 0, () => `lines match ${JSON.stringify(p)}: ${show(found)}\n${showRun(ctx.outcome)}`);
  }],
  ["Then", "stderr has no line matching {string}", (ctx, p) => {
    const found = lines(ctx.outcome?.stderr).filter((l) => matches(p, l));
    check(found.length === 0, () => `lines of stderr match ${JSON.stringify(p)}: ${show(found)}\n${showRun(ctx.outcome)}`);
  }],

  // Stand-in programs
  ["Given", "a stand-in {string}", (ctx, n) => { standins(ctx).add(n); refreshPath(ctx); }],
  ["Given", "a stand-in {string} that prints {string}", (ctx, n, t) => { standins(ctx).add(n, `${t}\n`); refreshPath(ctx); }],
  ["Given", "a stand-in {string} that prints:", (ctx, n, doc) => { standins(ctx).add(n, `${doc}\n`); refreshPath(ctx); }],
  ["Given", "a stand-in {string} that fails, saying {string}", (ctx, n, t) => { standins(ctx).add(n, "", `${t}\n`, 1); refreshPath(ctx); }],
  ["Given", "a stand-in {string} that answers in turn:", (ctx, n, table) => {
    const [keys, ...data] = rows(table);
    const answers = data.map((row) => {
      const a = Object.fromEntries(keys.map((k, i) => [k, row[i]]));
      for (const s of ["stdout", "stderr"]) if (a[s]) a[s] = a[s].replaceAll("\\n", "\n") + "\n";
      return a;
    });
    standins(ctx).addTurns(n, answers);
    refreshPath(ctx);
  }],
  ["Given", "a stand-in {string} that reads its input", (ctx, n) => { standins(ctx).addReader(n); refreshPath(ctx); }],
  ["Given", "only stand-ins are installed", (ctx) => { standins(ctx).only = true; refreshPath(ctx); }],
  ["Given", "{string} is not installed", (ctx, n) => { const s = standins(ctx); s.remove(n); s.only = true; refreshPath(ctx); }],
  ["Then", "{string} was run with {string}", (ctx, n, args) => { const runs = ctx.standins?.runs(n) ?? []; check(runs.some((r) => JSON.stringify(r) === JSON.stringify(split(args))), `${n} ran with ${show(runs)}`); }],
  ["Then", "{string} was run {int} times", (ctx, n, k) => { const runs = ctx.standins?.runs(n) ?? []; check(runs.length === k, `${n} ran ${runs.length} times`); }],
  ["Then", "{string} was not run", (ctx, n) => { const runs = ctx.standins?.runs(n) ?? []; check(runs.length === 0, `${n} ran with ${show(runs)}`); }],
  ["Then", "{string} was run with arguments matching {string}", (ctx, n, p) => { const runs = ctx.standins?.runs(n) ?? []; check(runs.some((r) => matches(p, r.join(" "))), `${n} ran with ${show(runs)}`); }],
  ["Then", "{string} was not run with arguments matching {string}", (ctx, n, p) => { const found = (ctx.standins?.runs(n) ?? []).filter((r) => matches(p, r.join(" "))); check(found.length === 0, `${n} ran with ${show(found)}`); }],
  ["Then", "{string} was run, in order, with arguments matching:", (ctx, n, doc) => {
    // Some runs, in this order, though others may come between them, match the lines one by one.
    const patterns = String(doc).split("\n").map((l) => l.trim()).filter(Boolean);
    const runs = (ctx.standins?.runs(n) ?? []).map((r) => r.join(" "));
    let i = 0;
    const missing = patterns.find((p) => {
      while (i < runs.length) if (matches(p, runs[i++])) return false;
      return true;
    });
    check(missing === undefined, () => `${n} ran with nothing matching ${JSON.stringify(missing)} in order; it ran: ${show(runs)}`);
  }],
  ["Then", "{string} read the input:", (ctx, n, doc) => { const got = ctx.standins?.inputs(n) ?? []; check(got.map((i) => i.replace(/\n$/, "")).includes(String(doc).replace(/\n$/, "")), `${n} read ${show(got)}`); }],
  ["Then", "{string} read input including {string}", (ctx, n, t) => { const got = ctx.standins?.inputs(n) ?? []; check(got.some((i) => i.includes(t)), `${n} read ${show(got)}`); }],
  ["Then", "nothing was run", (ctx) => { const runs = ctx.standins?.runs() ?? []; check(runs.length === 0, `ran: ${show(runs)}`); }],

  // HTTP: the service under test
  ["Given", "I am signed in as {string}", (ctx, email) => { ctx.headers[ctx.identityHeader] = email; }],
  ["Given", "I am not signed in", (ctx) => { delete ctx.headers[ctx.identityHeader]; }],
  ["Given", "requests carry the header {string} set to {string}", (ctx, h, v) => { ctx.headers[h.toLowerCase()] = v; }],
  ["Given", "requests come from {string}", (ctx, origin) => { ctx.headers.origin = origin; }],
  ["When", "I GET {string}", (ctx, p) => send(ctx, "GET", p)],
  ["When", "I POST to {string} with:", (ctx, p, doc) => send(ctx, "POST", p, String(doc), "application/json")],
  ["When", "I POST to {string} with the form:", (ctx, p, table) => {
    let data = rows(table);
    if (data[0]?.[0] === "field" && data[0]?.[1] === "value") data = data.slice(1);
    return send(ctx, "POST", p, new URLSearchParams(data.map(([k, v]) => [k, v])).toString(), "application/x-www-form-urlencoded");
  }],
  ["When", "I send {string} to {string}", (ctx, m, p) => send(ctx, m, p)],
  ["When", "I send {string} to {string} with:", (ctx, m, p, doc) => send(ctx, m, p, String(doc), "application/json")],
  ["When", "I send {string} to {string} with the file {string}", (ctx, m, p, f) => {
    const typed = Object.keys(ctx.headers).some((k) => k.toLowerCase() === "content-type");
    return send(ctx, m, p, fs.readFileSync(at(ctx, f)), typed ? undefined : "application/octet-stream");
  }],
  ["Then", "the answer is {int}", (ctx, s) => { const a = answer(ctx); check(a.status === s, () => showAnswer(a)); }],
  ["Then", "the answer's {string} is {string}", (ctx, h, v) => { const a = answer(ctx); check(a.header(h) === v, () => showAnswer(a)); }],
  ["Then", "the answer's {string} includes {string}", (ctx, h, t) => { const a = answer(ctx); const got = a.header(h); check(got !== undefined && got.includes(t), () => showAnswer(a)); }],
  ["Then", "the answer has no {string}", (ctx, h) => { const a = answer(ctx); check(a.header(h) === undefined, () => showAnswer(a)); }],
  ["Then", "the answer includes {string} once", (ctx, t) => { const a = answer(ctx); check(a.text.split("\n").filter((l) => l.includes(t)).length === 1, () => showAnswer(a)); }],
  ["Then", "the answer includes {string}", (ctx, t) => { const a = answer(ctx); check(a.text.includes(t), () => showAnswer(a)); }],
  ["Then", "the answer does not include {string}", (ctx, t) => { const a = answer(ctx); check(!a.text.includes(t), () => showAnswer(a)); }],
  ["Then", "the answer is the JSON:", (ctx, doc) => { const a = answer(ctx); check(same(a.json(), String(doc)), () => showAnswer(a)); }],
  ["Then", "the answer redirects to {string}", (ctx, p) => { const a = answer(ctx); check(a.status >= 300 && a.status < 400 && a.header("location") === p, () => showAnswer(a)); }],

  // HTTP: fake services
  ["Given", "a fake {string} service", (ctx, n) => fake(ctx, n)],
  ["Given", "the {string} service answers {string} with {int}", async (ctx, n, r, s) => (await fake(ctx, n)).answer(r, s)],
  ["Given", "the {string} service answers {string} with {int} and:", async (ctx, n, r, s, doc) => (await fake(ctx, n)).answer(r, s, String(doc))],
  ["Given", "the {string} service answers {string} with {int} and the header {string} set to {string}", async (ctx, n, r, s, h, v) => (await fake(ctx, n)).answer(r, s, "", { [h]: v })],
  ["Given", "the {string} service answers {string} with {int}, the header {string} set to {string}, and:", async (ctx, n, r, s, h, v, doc) => (await fake(ctx, n)).answer(r, s, String(doc), { [h]: v })],
  ["Then", "the {string} service was asked {string}", (ctx, n, r) => { const a = asked(ctx, n).map((q) => `${q.method} ${q.path}`); check(a.includes(r) || a.map((x) => x.split("?")[0]).includes(r), `${n} was asked ${show(a)}`); }],
  ["Then", "the {string} service was asked {string} {int} times", (ctx, n, r, k) => { const got = requests(ctx, n, r).length; check(got === k, `${n} was asked ${r} ${got} times`); }],
  ["Then", "the {string} service was asked {string} with the header {string} set to {string}", (ctx, n, r, h, v) => {
    const seen = requests(ctx, n, r).map((q) => q.headers[h.toLowerCase()]);
    check(seen.includes(v), `${n} was asked ${r} with ${h} ${show(seen)}`);
  }],
  ["Then", "the {string} service was asked {string} without the header {string}", (ctx, n, r, h) => {
    // It was asked METHOD PATH, and no such request carried the header.
    const found = requests(ctx, n, r);
    check(found.length > 0, `${n} was not asked ${r}`);
    const seen = found.map((q) => q.headers[h.toLowerCase()]).filter((v) => v !== undefined);
    check(seen.length === 0, `${n} was asked ${r} with ${h} ${show(seen)}`);
  }],
  ["Then", "every request to the {string} service carried the header {string} set to {string}", (ctx, n, h, v) => {
    const all = asked(ctx, n);
    check(all.length > 0, `${n} was asked nothing`);
    const wrong = all.filter((q) => q.headers[h.toLowerCase()] !== v).map((q) => `${q.method} ${q.path}: ${JSON.stringify(q.headers[h.toLowerCase()])}`);
    check(wrong.length === 0, `not every request to ${n} carried ${h} ${JSON.stringify(v)}: ${show(wrong)}`);
  }],
  ["Then", "the {string} service was sent:", (ctx, n, doc) => {
    const bodies = asked(ctx, n).map((q) => { try { return JSON.parse(q.body); } catch { return q.body; } });
    check(bodies.some((b) => same(b, String(doc))), `${n} was sent ${show(bodies)}`);
  }],
  ["Then", "the {string} service was asked nothing", (ctx, n) => check(asked(ctx, n).length === 0, `${n} was asked ${show(asked(ctx, n))}`)],
  ["Then", "nothing was sent", (ctx) => { const sent = Object.values(ctx.fakes).filter((f) => f.requests.length); check(sent.length === 0, `sent: ${sent.map((f) => f.name)}`); }],

  // Calls to outside services: NAME is a plugin's id, or a prefix ("github" is every github.* plugin)
  ["Given", "the {string} integration can't be reached", (ctx, n) => tape(ctx).fault(n, "no-answer")],
  ["Given", "the {string} integration does not answer in time", (ctx, n) => tape(ctx).fault(n, `slow ${NEVER}`)],
  ["Given", "the {string} integration answers {string} with {int} and:", (ctx, n, r, s, doc) => tape(ctx).fault(n, `status ${s}`, { where: r, body: String(doc) })],
  ["Given", "the {string} integration answers with {int}, then as recorded", (ctx, n, s) => tape(ctx).fault(n, `status ${s}`, { nth: "first" })],
  ["Given", "the {string} integration answers with what is not JSON", (ctx, n) => tape(ctx).fault(n, "malformed")],
  ["Given", "the cassette of {string}", (ctx, scenario) => tape(ctx).borrow(scenario)],
  ["Then", "the Caller slept {float} seconds", (ctx, n) => { const got = tape(ctx).clock.slept; check(Math.abs(got - n) < 1e-9, `the Caller slept ${got} seconds`); }],
  ["Then", "{string} was called {int} times", (ctx, n, k) => {
    // Each try counts: a call tried three times was called three times.
    const made = tape(ctx).requests.filter((p) => matchesName(n, p));
    check(made.length === k, `${n} was called ${made.length} times: ${show(tape(ctx).requests)}`);
  }],

  // Secrets
  ["Given", "the secret {string}", (ctx, v) => { ctx.secrets.push(v); }],
  ["Then", "no secret appears in what it produced", (ctx) => {
    check(ctx.secrets.length, "no secret was given: the step checks the values a Given named");
    const leaks = Object.entries(produced(ctx)).flatMap(([where, t]) => ctx.secrets.filter((s) => t.includes(s)).map((s) => `${JSON.stringify(s)} in ${where}`));
    check(leaks.length === 0, `a secret appears: ${leaks.join("; ")}`);
  }],

  // Git
  ["Given", "a git repository", (ctx) => { git(ctx, "init", "-q", "-b", "main"); git(ctx, "commit", "-q", "--allow-empty", "-m", "start"); }],
  ["Given", "a commit tagged {string}", (ctx, tag) => { git(ctx, "add", "-A"); git(ctx, "commit", "-q", "--allow-empty", "-m", tag); git(ctx, "tag", tag); }],
  ["Given", "the branch {string}", (ctx, b) => { git(ctx, "switch", "-q", "-c", b); }],
  ["Given", "everything is committed with the message {string}", (ctx, m) => { git(ctx, "add", "-A"); git(ctx, "commit", "-q", "--allow-empty", "-m", m); }],
  ["Given", "a bare remote {string}", (ctx, n) => {
    const parent = path.join(scenarioTemp(ctx), "pubtest-remotes");
    fs.mkdirSync(parent, { recursive: true });
    const remote = path.join(parent, `${n}.git`);
    gitIn(parent, "init", "-q", "--bare", "-b", "main", remote);
    git(ctx, "remote", "add", n, remote);
    git(ctx, "push", "-q", n, "HEAD");
  }],
  ["Then", "the last commit's message includes {string}", (ctx, t) => { const m = git(ctx, "log", "-1", "--format=%B"); check(m.includes(t), `the last commit's message is ${JSON.stringify(m)}`); }],
  ["Then", "the working tree is clean", (ctx) => { const st = git(ctx, "status", "--porcelain"); check(st === "", `the working tree has changes:\n${st}`); }],
  ["Then", "the tag {string} exists", (ctx, t) => { const tags = git(ctx, "tag", "--list").split("\n"); check(tags.includes(t), `the tags are ${show(tags)}`); }],
  ["Then", "the remote {string} has the branch {string}", (ctx, n, b) => check(git(ctx, "ls-remote", "--heads", n, b) !== "", `the remote ${n} has no branch ${b}`)],
];

function write(ctx, p, t) {
  const target = at(ctx, p);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, t);
}

function text(ctx, p) {
  const target = at(ctx, p);
  check(fs.existsSync(target), `there is no ${p}`);
  return fs.readFileSync(target, "utf8");
}

function arity(expression) {
  return (expression.match(/\{[a-z]+\}/g) ?? []).length + (expression.endsWith(":") ? 1 : 0);
}

// cucumber-js checks a step function's arity against its expression's
// parameters, so each wrapper takes exactly that many.
const WRAPPERS = [
  (s) => function () { return s(this.pubtest); },
  (s) => function (a) { return s(this.pubtest, a); },
  (s) => function (a, b) { return s(this.pubtest, a, b); },
  (s) => function (a, b, c) { return s(this.pubtest, a, b, c); },
  (s) => function (a, b, c, d) { return s(this.pubtest, a, b, c, d); },
  (s) => function (a, b, c, d, e) { return s(this.pubtest, a, b, c, d, e); },
  (s) => function (a, b, c, d, e, f) { return s(this.pubtest, a, b, c, d, e, f); },
];

/**
 * Define pubtest's steps with a runner's API: cucumber-js's module, or
 * quickpickle's (pass { runner: "quickpickle" }).
 *
 *   import * as cucumber from "@cucumber/cucumber";
 *   import { register } from "@sustenaut/pubtest";
 *   register(cucumber, { client: () => fromFetch(worker.fetch) });
 *
 * `client` makes the scenario's HTTP client; `identityHeader` is the header
 * a signed-in person's email comes in (X-Forwarded-Email). `customers` are the
 * test customers a suite records with ({ name, steps, setup, cleanup });
 * `network` is the transport record mode records through, the network unless a
 * suite's tests of recording say otherwise.
 */
export function register(api, { runner = "cucumber", client, identityHeader = "x-forwarded-email", customers = [], network } = {}) {
  const quick = runner === "quickpickle";
  const root = repository();
  const byName = Object.fromEntries(customers.map((c) => [c.name, c]));
  let found = null;
  let support = null;
  const session = async () => {
    if (found === null) {
      found = await settings(root);
      startSession(found);
      const warning = standInOnly(found, network === undefined);
      if (warning) console.error(warning);
    }
    return found;
  };
  const begin = async (world, info) => {
    world.pubtest = new Context();
    world.pubtest.identityHeader = identityHeader.toLowerCase();
    world.pubtest.repository = root;
    if (client) world.pubtest.client = client(world);
    world.attempt = (action) => world.pubtest.attempt(action);
    const harness = await session();
    if (!harness.active) return undefined;
    const scenario = await info();
    if (!scenario) return undefined;
    if (!selected(scenario.scenario)) return "skipped";
    const t = await transports();
    const tape = new Tape(t, harness, scenario.scenario, scenario.tags, textHash(scenario.steps), { network, customers: byName, steps: (support ??= supportHash(root)) });
    tape.begin();
    world.pubtest.tape = tape;
    return undefined;
  };
  // The scenario's end: its tape's (cassette, the scenario's own cleanups, its customers'
  // cleanups, in that order, before the harness's environment is restored), then its
  // unread refusal. A passed scenario fails with every problem; a failed one keeps its
  // own failure, and the problems after it are printed to stderr, as Python warns them.
  const end = async (world, failed) => {
    const ctx = world.pubtest;
    const problems = [];
    let thrown = null; // a cleanup's own error, thrown as it is when it is all that went wrong
    const close = async () => {
      try {
        await ctx.close();
      } catch (err) {
        thrown = err;
        throw err;
      }
    };
    if (ctx.tape) {
      ctx.tape.failed = failed;
      problems.push(...await ctx.tape.end(close));
    } else {
      try {
        await close();
      } catch (err) {
        problems.push(`a cleanup failed: ${err?.stack ?? err?.message ?? err}`);
      }
    }
    if (ctx.refused && !ctx.refusalRead) {
      problems.unshift(`the action was refused, and no step read it: ${ctx.refused.error?.stack ?? ctx.refused.message}`);
    } else if (failed) {
      if (problems.length) console.error(`pubtest: after the scenario failed:\n${problems.join("\n")}`);
      return;
    }
    if (problems.length === 1 && thrown) throw thrown;
    if (problems.length) throw new Error(problems.join("\n"));
  };
  if (quick) {
    api.BeforeAll(async () => { await session(); });
    api.Before(async (world) => {
      if (await begin(world, () => fromQuickpickle(world)) === "skipped") world.context.skip();
    });
    api.After(async (world) => end(world, (world.info.errors?.length ?? 0) > 0));
  } else {
    api.BeforeAll(async function () { await session(); });
    api.Before(async function (testCase) { return begin(this, async () => fromPickle(testCase.pickle, testCase.gherkinDocument)); });
    api.After(async function (testCase) { await end(this, testCase.result?.status === "FAILED"); });
  }
  const steps = [...STEPS, ...customers.flatMap((c) => c.steps ?? [])];
  for (const [kind, expression, step] of steps) {
    if (quick) api[kind](expression, async (world, ...args) => step(world.pubtest, ...args));
    else api[kind](expression, WRAPPERS[arity(expression)](step));
  }
}
