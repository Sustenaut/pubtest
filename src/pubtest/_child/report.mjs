// Loaded by every Node program a pubtest scenario runs (NODE_OPTIONS=--import):
// a program in replay answers its calls from INTEGRATIONS_CASSETTE through a
// Cassette of its own, installed with integrations' use(), and at exit writes
// which recorded calls it used to INTEGRATIONS_CASSETTE_REPORT, so the scenario
// fails on a recorded call no process made. integrations has no hook for this
// yet. @sustenaut/integrations is found from the program's working directory,
// else from here; a program that loads another copy of it is not reported.
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";

const report = process.env.INTEGRATIONS_CASSETTE_REPORT;
const file = process.env.INTEGRATIONS_CASSETTE;
if (report && file && process.env.INTEGRATIONS_MODE === "replay" && process.env.PUBTEST_RUN) {
  let transports = null;
  for (const from of [path.join(process.cwd(), "noop.js"), import.meta.url]) {
    try {
      transports = await import(pathToFileURL(createRequire(from).resolve("@sustenaut/integrations/transports.js")).href);
      break;
    } catch {
      // not there: the program makes no integration calls through this copy
    }
  }
  if (transports) {
    let cassette = null;
    transports.use({
      fetch: async (url, init) => {
        cassette ??= new transports.Cassette(transports.cassettePath(file), { mode: "replay" });
        return cassette.fetch(url, init);
      },
    });
    process.on("exit", () => {
      if (!cassette) return;
      const used = cassette.calls.flatMap((c, i) => (c.used ? [i] : []));
      const answered = cassette.calls.reduce((n, c) => n + c.used, 0);
      fs.appendFileSync(report, JSON.stringify({ pid: process.pid, language: "node", cassette: file, calls: cassette.calls.length, used, sent: cassette.sent.length, answered }) + "\n");
    });
  }
}
