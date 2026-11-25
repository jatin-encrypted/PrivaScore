/**
 * The app's four states (section 7.3), as a discriminated union plus a reducer.
 *
 *   idle --submit--> loading --200--> results
 *     ^                 |  \--error--> error --retry--> loading
 *     |                 \--cancel--> idle (the text is kept)
 *     \--"Analyze another policy" (clears the text and the results from memory)
 *
 * idle --open a saved analysis--> results (source: "example"); no loading state, because that
 * is a cached GET with no provider call behind it.
 *
 * The pasted text lives in this state and nowhere else: never in localStorage, sessionStorage,
 * IndexedDB, a cookie or the URL (section 7.8). It survives loading and error so a retry needs
 * no re-paste, and it is dropped on reset and when the tab closes.
 */
import type { ApiError, ErrorCode, EvaluateResponse, Scope } from "../api/client";

export type Input = { text: string; companyName: string; scope: Scope };

export type State =
  | { status: "idle"; input: Input }
  | { status: "loading"; input: Input; startedAt: number; controller: AbortController }
  | { status: "results"; input: Input; data: EvaluateResponse; source: "live" | "example" }
  | { status: "error"; input: Input; code: ErrorCode; retryAfterS: number | null };

export type Action =
  | { type: "edit"; patch: Partial<Input> }
  | { type: "submit"; startedAt: number; controller: AbortController }
  | { type: "succeeded"; data: EvaluateResponse; source?: "live" | "example" }
  | { type: "openedExample"; data: EvaluateResponse }
  | { type: "failed"; error: ApiError }
  | { type: "cancel" }
  | { type: "retry"; startedAt: number; controller: AbortController }
  | { type: "editText" }
  | { type: "reset" };

export const EMPTY_INPUT: Input = { text: "", companyName: "", scope: "all_users" };

export const initialState: State = { status: "idle", input: EMPTY_INPUT };

export function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "edit":
      // Editing is only meaningful on the input screen; ignore it while an analysis runs so a
      // stray keystroke cannot change what was submitted.
      if (state.status !== "idle") return state;
      return { status: "idle", input: { ...state.input, ...action.patch } };

    case "submit":
    case "retry":
      if (state.status === "loading") return state;
      return {
        status: "loading",
        input: state.input,
        startedAt: action.startedAt,
        controller: action.controller,
      };

    case "succeeded":
      if (state.status !== "loading") return state;
      return {
        status: "results",
        input: state.input,
        data: action.data,
        source: action.source ?? "live",
      };

    case "openedExample":
      // A saved analysis arrives from idle, not from "loading": it is a cached GET that takes
      // milliseconds, so it never shows the progress screen. The pasted input is left untouched
      // so closing the example returns the user to whatever they had typed.
      return {
        status: "results",
        input: state.input,
        data: action.data,
        source: "example",
      };

    case "failed":
      if (state.status !== "loading") return state;
      // A cancel arrives as an aborted fetch; it returns to idle, not to the error screen.
      if (action.error.code === "CANCELLED") return { status: "idle", input: state.input };
      return {
        status: "error",
        input: state.input,
        code: action.error.code,
        retryAfterS: action.error.retryAfterS,
      };

    case "cancel":
      if (state.status !== "loading") return state;
      state.controller.abort();
      return { status: "idle", input: state.input };

    case "editText":
      if (state.status !== "error") return state;
      return { status: "idle", input: state.input };

    case "reset":
      // "Analyze another policy": the result is gone from memory either way. A LIVE result also
      // clears the pasted text, which is section 7.8's requirement. Closing a saved example
      // instead keeps whatever the user had typed, because that draft was never analysed and
      // throwing it away would punish them for looking at an example.
      if (state.status === "results" && state.source === "example") {
        return { status: "idle", input: state.input };
      }
      return initialState;
  }
}

/** The Analyze button is enabled only inside the limits the backend enforces. */
export function inputProblem(
  text: string,
  limits: { minChars: number; maxChars: number },
): "too_short" | "too_long" | null {
  const normalised = text.replace(/\r\n?/g, "\n");
  if (normalised.trim().length < limits.minChars) return "too_short";
  if (normalised.length > limits.maxChars) return "too_long";
  return null;
}
