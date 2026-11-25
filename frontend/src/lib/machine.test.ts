import { describe, expect, it, vi } from "vitest";

import { ApiError, type EvaluateResponse } from "../api/client";
import { EMPTY_INPUT, inputProblem, initialState, reducer, type State } from "./machine";

const data = { api_version: "1" } as unknown as EvaluateResponse;
type Loading = Extract<State, { status: "loading" }>;
const loading = (input = { ...EMPTY_INPUT, text: "pasted" }): Loading => ({
  status: "loading",
  input,
  startedAt: 1000,
  controller: new AbortController(),
});

describe("the happy path", () => {
  it("goes idle -> loading -> results", () => {
    let s = reducer(initialState, { type: "edit", patch: { text: "pasted" } });
    expect(s.status).toBe("idle");
    s = reducer(s, { type: "submit", startedAt: 1000, controller: new AbortController() });
    expect(s.status).toBe("loading");
    s = reducer(s, { type: "succeeded", data });
    expect(s).toMatchObject({ status: "results", source: "live" });
  });

  it("keeps the pasted text through loading and results", () => {
    const s = reducer(loading(), { type: "succeeded", data });
    expect(s.input.text).toBe("pasted");
  });
});

describe("the text is only ever in memory", () => {
  it("is cleared by 'Analyze another policy'", () => {
    const s = reducer(reducer(loading(), { type: "succeeded", data }), { type: "reset" });
    expect(s).toEqual(initialState);
    expect(s.input.text).toBe("");
  });

  it("survives an error so a retry needs no re-paste", () => {
    const s = reducer(loading(), { type: "failed", error: new ApiError("LLM_QUOTA", 429, 60) });
    expect(s.status).toBe("error");
    expect(s.input.text).toBe("pasted");
  });

  it("survives a cancel", () => {
    const s = reducer(loading(), { type: "cancel" });
    expect(s.status).toBe("idle");
    expect(s.input.text).toBe("pasted");
  });
});

describe("cancelling", () => {
  it("aborts the in-flight request", () => {
    const state = loading();
    const spy = vi.spyOn(state.controller, "abort");
    reducer(state, { type: "cancel" });
    expect(spy).toHaveBeenCalledOnce();
  });

  it("treats an aborted fetch as a return to idle, not as an error", () => {
    const s = reducer(loading(), { type: "failed", error: new ApiError("CANCELLED") });
    expect(s.status).toBe("idle");
  });
});

describe("errors", () => {
  it("carries the code and Retry-After to the error screen", () => {
    const s = reducer(loading(), { type: "failed", error: new ApiError("BUSY", 429, 30) });
    expect(s).toMatchObject({ status: "error", code: "BUSY", retryAfterS: 30 });
  });

  it("goes back to the input screen on 'Edit text'", () => {
    const err = reducer(loading(), { type: "failed", error: new ApiError("LLM_ERROR", 502) });
    expect(reducer(err, { type: "editText" }).status).toBe("idle");
  });

  it("retries from the error screen without losing the text", () => {
    const err = reducer(loading(), { type: "failed", error: new ApiError("LLM_ERROR", 502) });
    const s = reducer(err, { type: "retry", startedAt: 2000, controller: new AbortController() });
    expect(s).toMatchObject({ status: "loading" });
    expect(s.input.text).toBe("pasted");
  });
});

describe("illegal transitions are ignored", () => {
  it("drops a late success after a cancel", () => {
    const idle = reducer(loading(), { type: "cancel" });
    expect(reducer(idle, { type: "succeeded", data }).status).toBe("idle");
  });

  it("drops a late failure after a cancel", () => {
    const idle = reducer(loading(), { type: "cancel" });
    expect(reducer(idle, { type: "failed", error: new ApiError("NETWORK") }).status).toBe("idle");
  });

  it("does not start a second analysis while one runs", () => {
    const state = loading();
    const again = reducer(state, { type: "submit", startedAt: 9999, controller: new AbortController() });
    expect(again).toBe(state);
  });

  it("ignores edits while loading, so the submitted text cannot change under it", () => {
    const state = loading();
    expect(reducer(state, { type: "edit", patch: { text: "something else" } })).toBe(state);
  });
});

describe("inputProblem", () => {
  const limits = { minChars: 1000, maxChars: 200_000 };

  it("flags text under the minimum, measured after trimming", () => {
    expect(inputProblem("short", limits)).toBe("too_short");
    expect(inputProblem(" ".repeat(5000), limits)).toBe("too_short");
  });

  it("flags text over the maximum", () => {
    expect(inputProblem("a".repeat(200_001), limits)).toBe("too_long");
  });

  it("accepts text inside the limits", () => {
    expect(inputProblem("a".repeat(1000), limits)).toBeNull();
  });

  it("counts CRLF the way the backend will, after normalisation", () => {
    // Raw length would be 1503, but the backend measures len(text.strip()) on the SAME
    // normalised string, so the client must too: 501 lines -> 1002 chars -> 1001 after trim.
    expect(inputProblem("a\r\n".repeat(501), limits)).toBeNull();
    // And one line fewer is 999 after the trailing newline is trimmed: still too short, in
    // both places. A client that trimmed differently would enable a button the backend 422s.
    expect(inputProblem("a\r\n".repeat(500), limits)).toBe("too_short");
  });
});
