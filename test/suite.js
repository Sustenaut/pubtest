// The steps a suite would write itself, for pubtest's own features: the
// same text as tests/conftest.py has in Python, defined with either runner.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { produced } from "../js/index.js";
import { STEPS } from "../js/steps.js";

process.env.GREET_BIN_DIR ??= path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "tests", "bin");

// The service under test in http.feature.
export async function app(request) {
  const url = new URL(request.url);
  const who = request.headers.get("x-forwarded-email");
  const text = (status, body, headers = {}) => new Response(body, { status, headers: { "content-type": "text/plain", ...headers } });
  if (url.pathname === "/hello") return who ? text(200, `hello, ${who}`) : text(403, "sign in");
  if (url.pathname === "/echo" && ["POST", "PUT"].includes(request.method)) {
    return new Response(JSON.stringify({ echo: await request.json() }), { headers: { "content-type": "application/json" } });
  }
  if (url.pathname === "/form" && request.method === "POST") {
    return text(200, [...new URLSearchParams(await request.text())].map(([k, v]) => `${k}=${v}`).join("&"));
  }
  if (url.pathname === "/old") return new Response("", { status: 302, headers: { location: "/new" } });
  if (url.pathname === "/forecast") {
    const asked = await fetch(`${process.env.WEATHER_URL}/today`, { headers: { "x-client": "pubtest-app" } });
    const sky = asked.headers.get("x-sky");
    return text(200, await asked.text(), sky ? { "x-sky": sky } : {});
  }
  if (url.pathname === "/upload") {
    const body = new Uint8Array(await request.arrayBuffer());
    return text(200, `${request.method} ${request.headers.get("content-type") ?? "-"} ${body.length} ${request.headers.get("x-token") ?? "-"}`);
  }
  return text(404, "");
}


/** Define the suite's steps with `define(kind, expression, fn)`, fn called with the World as this. */
export function suite(define) {

  define("When", "I add {int} and {int}", function (a, b) { return this.attempt(() => a + b); });
  define("When", "I check that {int} is more than {int}", function (a, b) { return this.attempt(() => a > b); });
  define("When", "I give back the text {string}", function (t) { return this.attempt(() => t); });
  define("Then", "the result is not the number 2", function () {
    if (this.pubtest.result !== "2") throw new Error(`the result is ${this.pubtest.result}`);
  });
  define("When", "I list the words of {string}", function (t) { return this.attempt(() => t.split(" ")); });
  define("When", "I list the people", function () { return this.attempt(() => [{ name: "Ann", age: 30 }, { name: "Ben", age: 41 }]); });
  define("When", "I find nothing", function () { return this.attempt(() => null); });
  define("When", "I divide {int} by {int}", function (a, b) {
    return this.attempt(() => {
      if (b === 0) throw new Error("division by zero");
      return a / b;
    });
  });

  class Problem extends Error {}
  class NotFound extends Problem {
    constructor(key) {
      super(`no ${key}`);
      this.key = key;
      this.detail = { code: 404 };
    }
  }
  define("When", "I look up {string}", function (key) { return this.attempt(() => { throw new NotFound(key); }); });
  define("When", "I describe the release", function () { return this.attempt(() => ({ version: "v1.2.3", tags: ["stable", "lts"], note: "" })); });

  function main(argv) {
    if (argv[0]?.startsWith("--")) {
      console.error("usage: main [NAME]");
      console.error(`no such option: ${argv[0]}`);
      process.exit(2);
    }
    console.log("ok");
  }

  define("When", "I copy {string} from the repository", function (src) {
    const [, , copy] = STEPS.find(([, expression]) => expression === "a file {string} copied from {string}");
    return this.attempt(() => copy(this.pubtest, "copy", src));
  });
  define("When", "I run main with {string}", function (args) { return this.attempt(() => main(args.split(" "))); });

  define("Then", "the secret is found in {string}", function (where) {
    const found = produced(this.pubtest)[where] ?? "";
    if (!this.pubtest.secrets.some((s) => found.includes(s))) throw new Error(JSON.stringify(produced(this.pubtest)));
  });

  define("When", "a scenario whose action is refused, and that reads {word} {word}, runs", function (a, b) {
    const reads = `${a} ${b}` === "no refusal" ? "Then nothing else is checked" : "Then it is refused";
    // Inside node_modules, so the inner suite finds @cucumber/cucumber; away from cucumber.json.
    const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
    const dir = fs.mkdtempSync(path.join(repo, "node_modules", ".pubtest-inner-"));
    this.pubtest.cleanup(() => fs.rmSync(dir, { recursive: true, force: true }));
    const js = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "js", "index.js");
    fs.writeFileSync(path.join(dir, "inner.feature"), `Feature: Inner\n  Scenario: Inner\n    When I divide 1 by 0\n    ${reads}\n`);
    fs.writeFileSync(path.join(dir, "inner.mjs"), `import * as cucumber from "@cucumber/cucumber";
import { register } from ${JSON.stringify(js)};
register(cucumber);
cucumber.When("I divide {int} by {int}", function (a, b) { return this.attempt(() => { if (b === 0) throw new Error("division by zero"); return a / b; }); });
cucumber.Then("nothing else is checked", function () {});
`);
    const bin = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "node_modules", "@cucumber", "cucumber", "bin", "cucumber.js");
    const done = spawnSync(process.execPath, [bin, "--import", path.join(dir, "inner.mjs"), path.join(dir, "inner.feature")],
      { cwd: dir, encoding: "utf8" });
    this.inner = done;
  });
  define("Then", "that scenario fails, saying {string}", function (t) {
    const said = this.inner.stdout + this.inner.stderr;
    if (this.inner.status === 0 || !said.includes(t)) throw new Error(said);
  });
  define("Then", "that scenario passes", function () {
    if (this.inner.status !== 0) throw new Error(this.inner.stdout + this.inner.stderr);
  });
}
