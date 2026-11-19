// Types for @sustenaut/pubtest (index.js): the steps every Sustenaut suite shares (GRAMMAR.md).
import type { Answer, Client } from "./http.js";

export { Answer, fromFetch, fromUrl } from "./http.js";
export type { Body, Client } from "./http.js";

/** What an action raised. */
export class Refused {
  constructor(error: unknown);
  error: unknown;
  /** Its message; empty for a process.exit. */
  readonly message: string;
}

/** What a scenario's action came to, whichever kind of When it was. */
export class Result {
  constructor(fields?: Partial<Pick<Result, "value" | "refused" | "code" | "stdout" | "stderr" | "argv">>);
  value: unknown;
  refused: Refused | null;
  code: number;
  stdout: string;
  stderr: string;
  argv: string[];
  describe(): string;
}

/** A scenario's state (the World's `pubtest`), and the cleanups that run when it ends, in reverse. */
export class Context {
  outcome: Result | null;
  refusalRead: boolean;
  directory: string | null;
  secrets: string[];
  written: Record<string, string> | null;
  headers: Record<string, string>;
  programs: Record<string, string>;
  fakes: Record<string, unknown>;
  recorded: unknown[];
  standins: unknown;
  answer: Answer | null;
  cleanups: Array<() => unknown>;
  client?: Client;
  identityHeader?: string;
  repository?: string;
  /** The value the action returned. */
  readonly result: unknown;
  /** The refusal it raised, or null. */
  readonly refused: Refused | null;
  /** Run `fn` when the scenario ends. */
  cleanup<F extends () => unknown>(fn: F): F;
  /** Before an action: the scratch directory as it was before the first one. */
  acting(): void;
  /** Do the scenario's action: keep what it returns or raises, and what it printed. */
  attempt<T>(action: () => T | Promise<T>): Promise<T | undefined>;
  /** Keep a program's run as what the action came to. */
  ran(outcome: Result): Result;
  close(): Promise<void>;
}

/** A step: its kind, its cucumber expression, and what it does with the scenario's context. */
export type Step = [kind: "Given" | "When" | "Then", expression: string, run: (ctx: Context, ...args: any[]) => unknown];

/** pubtest's steps. */
export const STEPS: Step[];

export interface RegisterOptions {
  /** "cucumber" (the default) or "quickpickle". */
  runner?: "cucumber" | "quickpickle";
  /** Makes the scenario's HTTP client, given the World. */
  client?: (world: any) => Client;
  /** The header a signed-in person's email comes in (x-forwarded-email). */
  identityHeader?: string;
}

/** Define pubtest's steps with a runner's API: cucumber-js's module, or quickpickle's. */
export function register(api: any, options?: RegisterOptions): void;

/** Everything the action produced, by where it went: what `no secret appears` reads. */
export function produced(ctx: Context): Record<string, string>;

/** Whether `actual` is a step's value V, by the one rule GRAMMAR.md gives. */
export function same(actual: unknown, wanted: string): boolean;

/** The value at a dotted key: a.b.0 is data.a.b[0]. */
export function dig(data: unknown, key: string): any;

/** Text contains it, a list holds it, a map has it as a key. */
export function includes(container: unknown, item: string): boolean;

/** Split a command as a POSIX shell splits words. */
export function split(command: string): string[];
