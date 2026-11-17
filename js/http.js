// Adapters that let pubtest's HTTP steps send a suite's service a request.
// A suite constructs one and gives it to pubtest (`useClient`); pubtest only
// calls it, with a method, a path, headers and a body, and reads back a
// status, headers (compared without case) and a body. Redirects are not
// followed.

/** An answer: status, headers, and the body as text, its JSON read on demand. */
export class Answer {
  constructor(status, headers, text) {
    this.status = status;
    this.headers = Object.fromEntries(Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v]));
    this.text = text;
  }
  header(name) {
    return this.headers[name.toLowerCase()];
  }
  json() {
    return JSON.parse(this.text);
  }
}

/** A Cloudflare Worker's or any fetch(request) handler, called directly. */
export function fromFetch(handler, base = "http://localhost") {
  return async (method, path, headers, body) => {
    const request = new Request(new URL(path, base), { method, headers, body: body ?? undefined, redirect: "manual" });
    const response = await handler(request);
    return new Answer(response.status, Object.fromEntries(response.headers.entries()), await response.text());
  };
}

/** A server already listening, at a base URL. */
export function fromUrl(base) {
  return async (method, path, headers, body) => {
    const response = await fetch(new URL(path, base), { method, headers, body: body ?? undefined, redirect: "manual" });
    return new Answer(response.status, Object.fromEntries(response.headers.entries()), await response.text());
  };
}
