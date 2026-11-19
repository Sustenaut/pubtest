// Types for @sustenaut/pubtest/http (http.js).

/** What a service answered: its status, its headers (names in lower case), and its body as text. */
export class Answer {
  constructor(status: number, headers: Record<string, string>, text: string);
  status: number;
  headers: Record<string, string>;
  text: string;
  /** A header, its name compared without case. */
  header(name: string): string | undefined;
  /** The body read as JSON. */
  json(): unknown;
}

/** A request's body, as the HTTP steps send it. */
export type Body = string | Uint8Array | null | undefined;

/** What pubtest calls to send the service under test a request. Redirects are not followed. */
export type Client = (method: string, path: string, headers: Record<string, string>, body?: Body) => Promise<Answer>;

/** A Cloudflare Worker's or any fetch(request) handler, called directly. */
export function fromFetch(handler: (request: Request) => Response | Promise<Response>, base?: string): Client;

/** A server already listening, at a base URL. */
export function fromUrl(base: string | URL): Client;
