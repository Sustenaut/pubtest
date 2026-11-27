// Types for @sustenaut/pubtest/cassettes (cassettes.js): record and replay (GRAMMAR.md, "Record and replay").

export const RECORD: "PUBTEST_RECORD";
export const SWITCH: "PUBTEST_CASSETTES";
export const ONLY: "PUBTEST_ONLY";
export const PLAN: "PUBTEST_PLAN";
export const REPORT: "INTEGRATIONS_CASSETTE_REPORT";
export const RUN: "PUBTEST_RUN";
export const MODE: "INTEGRATIONS_MODE";
export const CASSETTE: "INTEGRATIONS_CASSETTE";
export const CASSETTES: "INTEGRATIONS_CASSETTES";
export const NO_DATA_REPO: string;
export const NEVER: number;

/** integrations' transports.js, or null when @sustenaut/integrations is not installed. */
export function transports(): Promise<any | null>;

/** A scenario's title as a file name. */
export function slug(title: string): string;

/** A scenario as a cassette names it. */
export class Scenario {
  constructor(feature: string, title: string, row?: number | null);
  feature: string;
  title: string;
  row: number | null;
  readonly stem: string;
  /** "FILE.feature: TITLE[ #ROW]" */
  readonly id: string;
  /** "<stem>/<slug>.json", or "<stem>/<slug>/<row>.json" */
  readonly relative: string;
  namedBy(selector: string): boolean;
}

/** A scenario from "FILE: TITLE[ #ROW]", or a TITLE of feature's. */
export function parse(selector: string, feature?: string | null): Scenario;

export interface Settings {
  active: boolean;
  mode: "replay" | "record";
  root: string;
  cassettes: string;
  dataRepo: string | null;
  /** The cassettes directory is pubrules.json's "DIR", in the repository itself. */
  named: boolean;
  readonly recording: boolean;
}

export function settings(root: string, env?: Record<string, string | undefined>): Promise<Settings>;
export function startSession(found: Settings): void;
/** The warning a recording through the real network into pubrules.json's "DIR" gives, or null. */
export function standInOnly(found: Settings, realNetwork: boolean): string | null;
export function pathFor(scenario: Scenario, found: Settings): string;
/** NAME is a plugin's id, or what every id it stands for starts with, before a dot. */
export function matchesName(name: string, plugin: string | null | undefined): boolean;

/** The scenario's clock (ms), sleep (s) and jitter. */
export class Clock {
  constructor(fake: boolean);
  fake: boolean;
  slept: number;
  now(): number;
  sleep(seconds: number): Promise<void>;
  advance(seconds: number): void;
  random(): number;
}

/** A test customer: its steps, and its record-time setup and cleanup. */
export interface Customer {
  name: string;
  steps?: Array<[kind: "Given" | "When" | "Then", expression: string, run: (ctx: any, ...args: any[]) => unknown]>;
  /** Record mode only: the real names the scenario's logical ones stand for. */
  setup?(tape: Tape): Record<string, string> | Promise<Record<string, string>>;
  /** Record mode only, when the scenario ends, passed or failed: after its cassette is saved and its own
   * cleanups ran, with its INTEGRATIONS_* environment still set, calling through the record transport,
   * unrecorded (GRAMMAR.md, "When a scenario ends"). */
  cleanup?(tape: Tape, names: Record<string, string>): unknown;
}

/** One scenario's calls: its cassette, faults, clock and requests. */
export class Tape {
  scenario: Scenario;
  path: string;
  borrowed: string | null;
  clock: Clock;
  /** Each request's plugin, in order, each try counted. */
  requests: Array<string | null>;
  names: Record<string, Record<string, string>>;
  borrow(selector: string): void;
  fault(name: string, effect: string, options?: { nth?: string; where?: string; body?: string }): void;
  namesOf(customer: string): Promise<Record<string, string>>;
  fetch(url: string, init?: any): Promise<Response>;
}

/** The options a suite's own Caller takes, so the scenario's clock is its clock. */
export function callerOptions(ctx: any): { clock?: () => number; sleep?: (seconds: number) => Promise<void>; random?: () => number };
