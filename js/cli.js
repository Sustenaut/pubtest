#!/usr/bin/env node
// `pubtest record`: record the cassettes of a suite's scenarios (GRAMMAR.md, "Record and
// replay"): src/pubtest/cli.py for Node.
//
//   pubtest record --all                 every scenario
//   pubtest record --changed             the scenarios whose cassette is out of date
//   pubtest record "FILE: TITLE" ...     these scenarios
//   pubtest record --rename OLD NEW      move a scenario's cassette to its new name
//
// It runs the repository's suite with PUBTEST_RECORD=1: cucumber-js for a Node
// repository, pytest-bdd for a Python one (pubrules.json's ci.language, else Node).
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { CASSETTE, CASSETTES, MODE, NO_DATA_REPO, ONLY, parse, pathFor, PLAN, RECORD, REPORT, RUN, settings, SWITCH } from "./cassettes.js";
import { byCodeUnit, onPath, repository } from "./core.js";

const HARNESS = [RUN, MODE, CASSETTE, CASSETTES, REPORT, ONLY, PLAN, RECORD];
const USAGE = `pubtest record [--all | --changed | SCENARIO...] [--rename OLD NEW] [--create-data-repo]

  --all               every scenario
  --changed           the scenarios whose cassette is out of date
  SCENARIO            "FILE.feature: TITLE[ #ROW]"
  --rename OLD NEW    move OLD's cassette to NEW
  --create-data-repo  create the data repository with gh`;

function fail(message, code = 2) {
  console.error(`pubtest record: ${message}`);
  return code;
}

function harnessFree() {
  const env = { ...process.env };
  if (env[RUN]) for (const key of HARNESS) delete env[key];
  env[SWITCH] = "1";
  return env;
}

function language(root) {
  try {
    const found = JSON.parse(fs.readFileSync(path.join(root, "pubrules.json"), "utf8"))?.ci?.language;
    if (found === "python") return "python";
  } catch {
    // no pubrules.json: this program's own language
  }
  return "node";
}

/** The suite's command, and where it runs. */
export function runner(root, lang) {
  if (lang === "python") {
    const here = fs.existsSync(path.join(root, "tests", "pytest.ini")) ? path.join(root, "tests") : root;
    const venv = path.join(root, ".venv", "bin", "python");
    return [[fs.existsSync(venv) ? venv : onPath("python3"), "-m", "pytest", "-q", "-p", "no:cacheprovider"], here];
  }
  for (const from of [path.join(root, "noop.js"), import.meta.url]) {
    try {
      const bin = path.join(path.dirname(createRequire(from).resolve("@cucumber/cucumber/package.json")), "bin", "cucumber.js");
      return [[process.execPath, bin], root];
    } catch {
      // not installed there
    }
  }
  return [[onPath("npx"), "cucumber-js"], root];
}

function gitOut(root, ...args) {
  const git = onPath("git");
  if (git === null) return "";
  const done = spawnSync(git, args, { cwd: root, encoding: "utf8" });
  return done.status === 0 ? done.stdout.trim() : "";
}

function quote(word) {
  return /^[\w@%+=:,./-]+$/.test(word) ? word : `'${word.replaceAll("'", "'\\''")}'`;
}

/** Make sure the cassettes directory is there: a directory of the repository's own is
 * made; a missing data repository is created with gh only when asked. */
function dataRepo(found, create) {
  if (fs.existsSync(found.cassettes)) return 0;
  if (found.dataRepo === null || fs.existsSync(found.dataRepo)) {
    fs.mkdirSync(found.cassettes, { recursive: true });
    return 0;
  }
  const origin = gitOut(found.root, "remote", "get-url", "origin").replace(/\.git$/, "").split(/[/:]/);
  const owner = origin.length >= 2 ? origin.at(-2) : "OWNER";
  const name = path.basename(found.dataRepo);
  const command = ["gh", "repo", "create", `${owner}/${name}`, "--private", "--clone", "--description", `The recorded answers ${path.basename(found.root)}'s tests replay`];
  if (!create) {
    console.error(`no data repo at ${found.dataRepo}. Create it, private and beside this repository, with:\n\n  (cd ${path.dirname(found.root)} && ${command.map(quote).join(" ")})\n\nor run pubtest record again with --create-data-repo, which runs that and commits its README, pubrules.json and integrations.json.`);
    return 1;
  }
  const gh = onPath("gh");
  if (gh === null) return fail("gh repo create needs gh, which is not on PATH", 1);
  const done = spawnSync(gh, command.slice(1), { cwd: path.dirname(found.root), stdio: "inherit" });
  if (done.status !== 0 || !fs.existsSync(found.dataRepo)) return fail("gh repo create failed", done.status || 1);
  const repo = found.dataRepo;
  const of = path.basename(found.root);
  fs.writeFileSync(path.join(repo, "README.md"), `# ${name}\n\nThe recorded answers ${of}'s tests replay: one cassette per scenario under\n\`integrations/cassettes/\`, in integrations' \`integrations.cassette/1\` format,\nwritten by \`pubtest record\` in ${of}. Private: a recording holds no secret,\nbut it does hold what the services answered.\n`);
  fs.writeFileSync(path.join(repo, "pubrules.json"), `${JSON.stringify({ kind: "content" }, null, 2)}\n`);
  fs.writeFileSync(path.join(repo, "integrations.json"), `${JSON.stringify({ uses: [], exclude: [{ path: "**", reason: "Recorded answers, not code" }] }, null, 2)}\n`);
  fs.mkdirSync(found.cassettes, { recursive: true });
  fs.writeFileSync(path.join(found.cassettes, ".gitkeep"), "");
  const git = onPath("git");
  if (git === null) return fail("git is not on PATH", 1);
  for (const args of [["add", "-A"], ["commit", "-q", "-m", "Start the data repository"], ["push", "-q", "-u", "origin", "HEAD"]]) {
    if (spawnSync(git, args, { cwd: repo, stdio: "inherit" }).status !== 0) return fail(`git ${args.join(" ")} failed in ${repo}`, 1);
  }
  return 0;
}

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(path.join(dir, e.name)) : e.name.endsWith(".json") ? [path.join(dir, e.name)] : []));
}

function find(found, selector) {
  try {
    return parse(selector);
  } catch {
    // a title: look among the recorded ones
  }
  const hits = [];
  for (const file of fs.existsSync(found.cassettes) ? walk(found.cassettes).sort(byCodeUnit) : []) {
    try {
      const scenario = parse(JSON.parse(fs.readFileSync(file, "utf8")).scenario ?? "");
      if (scenario.namedBy(selector)) hits.push(scenario);
    } catch {
      // not a cassette
    }
  }
  if (hits.length !== 1) throw new Error(`"${selector}" names ${hits.length} recorded scenarios: write it "FILE.feature: TITLE"`);
  return hits[0];
}

function rename(found, oldName, newName) {
  let before;
  let after;
  try {
    before = find(found, oldName);
    after = parse(newName, before.feature);
  } catch (err) {
    return fail(err.message);
  }
  const [source, target] = [pathFor(before, found), pathFor(after, found)];
  if (!fs.existsSync(source)) return fail(`${before.id} has no cassette: there is no ${source}`);
  if (fs.existsSync(target)) return fail(`${after.id} has a cassette already: ${target}`);
  const root = fs.realpathSync(found.cassettes);
  const inside = path.relative(root, path.resolve(target));
  if (inside.startsWith("..") || path.isAbsolute(inside)) return fail(`${target} is outside the cassettes directory ${root}`);
  const data = JSON.parse(fs.readFileSync(source, "utf8"));
  data.scenario = after.id;
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, `${JSON.stringify(data, null, 1)}\n`);
  fs.rmSync(source);
  for (const dir of [path.dirname(source), path.dirname(path.dirname(source))]) {
    if (path.resolve(dir) !== path.resolve(found.cassettes) && fs.existsSync(dir) && fs.readdirSync(dir).length === 0) fs.rmdirSync(dir);
  }
  console.log(`${path.relative(found.cassettes, source)} -> ${path.relative(found.cassettes, target)}`);
  return 0;
}

/** The scenarios whose cassette is out of date: the suite runs in replay and each
 * scenario says whether it needs recording again. */
function changed(command, where) {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), "pubtest-plan-"));
  try {
    const plan = path.join(work, "plan.jsonl");
    spawnSync(command[0], command.slice(1), { cwd: where, env: { ...harnessFree(), [PLAN]: plan }, stdio: ["ignore", "ignore", "inherit"] });
    if (!fs.existsSync(plan)) return null;
    const found = new Map();
    for (const line of fs.readFileSync(plan, "utf8").split("\n").filter((l) => l.trim())) {
      const entry = JSON.parse(line);
      if (entry.changed) found.set(entry.scenario, entry.changed);
    }
    for (const [scenario, reason] of found) console.log(`${scenario}: ${reason}`);
    return [...found.keys()];
  } finally {
    fs.rmSync(work, { recursive: true, force: true });
  }
}

export async function record(argv) {
  const args = { all: false, changed: false, rename: null, create: false, scenarios: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--all") args.all = true;
    else if (a === "--changed") args.changed = true;
    else if (a === "--create-data-repo") args.create = true;
    else if (a === "--rename") {
      if (i + 2 >= argv.length) return fail("--rename takes OLD and NEW");
      args.rename = [argv[i + 1], argv[i + 2]];
      i += 2;
    } else if (a === "-h" || a === "--help") {
      console.log(USAGE);
      return 0;
    } else if (a.startsWith("--")) return fail(`no option ${a}\n${USAGE}`);
    else args.scenarios.push(a);
  }
  const root = repository();
  const found = await settings(root, harnessFree());
  if (args.rename) {
    if (args.all || args.changed || args.scenarios.length) return fail("--rename moves one cassette, and records nothing");
    return rename(found, ...args.rename);
  }
  if (!args.all && !args.changed && !args.scenarios.length) return fail("say which: --all, --changed, or the scenarios");
  if ((args.all && args.changed) || ((args.all || args.changed) && args.scenarios.length)) return fail("--all and --changed take no scenarios, nor each other");
  const made = dataRepo(found, args.create);
  if (made) return made;
  const [command, where] = runner(root, language(root));
  if (command[0] === null) return fail(`the suite runs with ${language(root) === "python" ? "python3" : "npx"}, which is not on PATH`, 1);
  let chosen = args.all ? null : args.scenarios;
  if (args.changed) {
    chosen = changed(command, where);
    if (chosen === null) return fail("the suite said nothing about its scenarios: is pubtest's harness on in it?", 1);
    if (!chosen.length) {
      console.log("no scenario's cassette is out of date");
      return 0;
    }
  }
  const env = { ...harnessFree(), [RECORD]: "1" };
  if (chosen !== null) env[ONLY] = JSON.stringify(chosen);
  const stamps = () => new Map(walk(found.cassettes).map((f) => { const st = fs.statSync(f, { bigint: true }); return [f, `${st.mtimeNs} ${st.size}`]; }));
  const before = stamps();
  const done = spawnSync(command[0], command.slice(1), { cwd: where, env, stdio: "inherit" });
  for (const [file, stamp] of [...stamps()].sort(([a], [b]) => (a < b ? -1 : 1))) {
    if (before.get(file) !== stamp) console.log(`recorded ${path.relative(found.cassettes, file)}`);
  }
  return done.status ?? 1;
}

export async function main(argv = process.argv.slice(2)) {
  if (!argv.length || argv[0] === "-h" || argv[0] === "--help") {
    console.log(USAGE);
    return argv.length ? 0 : 2;
  }
  if (argv[0] !== "record") return fail(`no command "${argv[0]}": pubtest record`);
  return record(argv.slice(1));
}

if (process.argv[1] && fs.realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main();
}
