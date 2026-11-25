/**
 * The only module that talks to the backend. Types come from src/api/schema.d.ts, which is
 * generated from the backend's /openapi.json (`npm run gen:api`), so the two cannot drift.
 */
import type { components } from "./schema";

export type EvaluateResponse = components["schemas"]["EvaluateResponse"];
export type EvaluateRequest = components["schemas"]["EvaluateRequest"];
export type FlagResult = components["schemas"]["FlagResult"];
export type Evidence = components["schemas"]["Evidence"];
export type Paragraph = components["schemas"]["Paragraph"];
export type Scores = components["schemas"]["Scores"];
export type Metrics = components["schemas"]["Metrics"];
export type Scope = EvaluateRequest["scope"];

/** The error codes the backend can return (section 6.9), plus the two the client adds itself. */
export type ErrorCode =
  | "INVALID_REQUEST" | "TEXT_TOO_SHORT" | "TEXT_TOO_LONG" | "BODY_TOO_LARGE"
  | "BUSY" | "LLM_QUOTA" | "LLM_OVERLOADED" | "LLM_ERROR" | "NOT_FOUND" | "INTERNAL"
  | "NETWORK" | "CANCELLED";

export class ApiError extends Error {
  constructor(
    readonly code: ErrorCode,
    readonly status: number | null = null,
    readonly retryAfterS: number | null = null,
  ) {
    super(code);
    this.name = "ApiError";
  }
}

const BASE = import.meta.env.VITE_API_BASE ?? "";

/** Worst case is roughly two LLM calls at 120 s each plus waits (section 6.10). */
export const REQUEST_TIMEOUT_MS = 300_000;

/** Line-ending normalisation. The backend applies exactly the same one, and every offset in
 *  the response refers to this string, so the source view must use it too (section 7.7). */
export function normaliseText(raw: string): string {
  return raw.replace(/\r\n?/g, "\n");
}

/** Maps a failed response to one of the fixed codes. Provider or server text is never shown. */
async function toApiError(res: Response): Promise<ApiError> {
  let code: ErrorCode = "INTERNAL";
  let retryAfter: number | null = null;
  try {
    const body = (await res.json()) as { error?: { code?: string; retry_after_s?: number | null } };
    if (body.error?.code) code = body.error.code as ErrorCode;
    retryAfter = body.error?.retry_after_s ?? null;
  } catch {
    // A non-JSON body (a proxy error page, say) stays INTERNAL.
    if (res.status === 404) code = "NOT_FOUND";
  }
  const header = res.headers.get("Retry-After");
  if (retryAfter === null && header && /^\d+$/.test(header)) retryAfter = Number(header);
  return new ApiError(code, res.status, retryAfter);
}

async function request<T>(path: string, init: RequestInit, signal?: AbortSignal): Promise<T> {
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, signal: combined });
  } catch (e) {
    // A user cancel and a lost connection both land here; only the first is the user's doing.
    if (signal?.aborted) throw new ApiError("CANCELLED");
    throw new ApiError("NETWORK");
  }
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

export function evaluate(
  body: { text: string; companyName?: string; scope?: Scope },
  signal?: AbortSignal,
): Promise<EvaluateResponse> {
  const payload: EvaluateRequest = {
    text: normaliseText(body.text),
    company_name: body.companyName?.trim() || null,
    scope: body.scope ?? "all_users",
  };
  return request<EvaluateResponse>(
    "/api/v1/evaluate",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) },
    signal,
  );
}

/** Only the slice of /meta the UI needs. The limits are the backend's, so the Analyze button
 *  and the live counter enforce exactly what the server will. */
export type Meta = {
  limits: { min_chars: number; max_chars: number; max_body_bytes: number; max_concurrent: number };
  provider: string;
  model: string;
};

export function getMeta(signal?: AbortSignal): Promise<Meta> {
  return request<Meta>("/api/v1/meta", { method: "GET" }, signal);
}

export type ExampleList = components["schemas"]["ExampleList"];
export type ExampleSummary = components["schemas"]["ExampleSummary"];

/** The saved gold-set analyses. These cost no provider call, so the input screen can show real
 *  results immediately instead of asking for 1,000 characters before it shows anything. */
export function getExamples(signal?: AbortSignal): Promise<ExampleList> {
  return request<ExampleList>("/api/v1/examples", { method: "GET" }, signal);
}

/** One saved analysis, in the same shape as a live one. It carries `document.text`, which a
 *  live response never does, because the browser did not supply the policy in this case. */
export function getExample(policyId: string, signal?: AbortSignal): Promise<EvaluateResponse> {
  return request<EvaluateResponse>(
    `/api/v1/examples/${encodeURIComponent(policyId)}`,
    { method: "GET" },
    signal,
  );
}
