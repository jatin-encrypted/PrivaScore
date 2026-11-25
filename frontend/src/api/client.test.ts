import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, evaluate, normaliseText } from "./client";

function mockFetch(res: Partial<Response> & { json?: () => Promise<unknown> }) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: res.ok ?? false,
    status: res.status ?? 500,
    headers: res.headers ?? new Headers(),
    json: res.json ?? (() => Promise.reject(new Error("not json"))),
  }));
}

const body = { text: "a".repeat(1000) };

afterEach(() => vi.unstubAllGlobals());

describe("normaliseText", () => {
  it("turns CRLF and lone CR into LF, and nothing else", () => {
    expect(normaliseText("a\r\nb\rc\nd")).toBe("a\nb\nc\nd");
  });

  it("leaves other characters, including emoji and curly quotes, untouched", () => {
    const t = "we ‘may’ share 😀 data";
    expect(normaliseText(t)).toBe(t);
  });
});

describe("error mapping", () => {
  it("maps the backend's error code and Retry-After", async () => {
    mockFetch({
      status: 429,
      headers: new Headers({ "Retry-After": "60" }),
      json: () => Promise.resolve({ error: { code: "LLM_QUOTA", retry_after_s: 60 } }),
    });
    await expect(evaluate(body)).rejects.toMatchObject({ code: "LLM_QUOTA", status: 429, retryAfterS: 60 });
  });

  it("maps 503 to LLM_OVERLOADED", async () => {
    mockFetch({
      status: 503,
      json: () => Promise.resolve({ error: { code: "LLM_OVERLOADED", retry_after_s: 120 } }),
    });
    await expect(evaluate(body)).rejects.toMatchObject({ code: "LLM_OVERLOADED", retryAfterS: 120 });
  });

  it("falls back to the Retry-After header when the body has no retry_after_s", async () => {
    mockFetch({
      status: 429,
      headers: new Headers({ "Retry-After": "30" }),
      json: () => Promise.resolve({ error: { code: "BUSY" } }),
    });
    await expect(evaluate(body)).rejects.toMatchObject({ code: "BUSY", retryAfterS: 30 });
  });

  it("stays INTERNAL for a non-JSON error body, such as a proxy page", async () => {
    mockFetch({ status: 502 });
    await expect(evaluate(body)).rejects.toMatchObject({ code: "INTERNAL", status: 502 });
  });

  it("reports a lost connection as NETWORK", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(evaluate(body)).rejects.toMatchObject({ code: "NETWORK" });
  });

  it("reports a user cancel as CANCELLED, not as a network failure", async () => {
    const controller = new AbortController();
    controller.abort();
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new DOMException("aborted", "AbortError")));
    await expect(evaluate(body, controller.signal)).rejects.toMatchObject({ code: "CANCELLED" });
  });
});

describe("the request body", () => {
  it("normalises the text and sends null for an empty company name", async () => {
    const f = vi.fn().mockResolvedValue({ ok: true, status: 200, headers: new Headers(), json: () => Promise.resolve({}) });
    vi.stubGlobal("fetch", f);
    await evaluate({ text: "line\r\nline", companyName: "  ", scope: "consumer" });
    const sent = JSON.parse(String(f.mock.calls[0]?.[1]?.body));
    expect(sent).toEqual({ text: "line\nline", company_name: null, scope: "consumer" });
  });

  it("defaults the scope to all_users", async () => {
    const f = vi.fn().mockResolvedValue({ ok: true, status: 200, headers: new Headers(), json: () => Promise.resolve({}) });
    vi.stubGlobal("fetch", f);
    await evaluate({ text: "x" });
    expect(JSON.parse(String(f.mock.calls[0]?.[1]?.body)).scope).toBe("all_users");
  });
});

describe("ApiError", () => {
  it("is an Error with a code", () => {
    const e = new ApiError("BUSY", 429, 30);
    expect(e).toBeInstanceOf(Error);
    expect(e.code).toBe("BUSY");
  });
});
