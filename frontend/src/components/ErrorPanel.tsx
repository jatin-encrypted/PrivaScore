import type { ErrorCode } from "../api/client";
import { copy } from "../lib/copy";
import { num } from "../lib/format";
import { Button } from "./ui/Button";

/**
 * Screen D (section 7.4). The error replaces the loading view and the pasted text is kept, so
 * "Try again" needs no re-paste. role="alert" so it is announced once.
 *
 * Only the fixed codes from section 6.9 are shown; no provider or server message ever reaches
 * this component, because the backend does not send one.
 */
export function ErrorPanel({
  code,
  limits,
  onRetry,
  onEditText,
}: {
  code: ErrorCode;
  limits: { minChars: number; maxChars: number };
  onRetry: () => void;
  onEditText: () => void;
}) {
  return (
    <div className="mx-auto max-w-[880px]" role="alert">
      <h1 className="t-h2">{copy.errors.headings[code]}</h1>
      <p className="t-body mt-4 text-ink-2">{errorMessage(code, limits)}</p>
      <div className="mt-8 flex flex-wrap gap-4">
        <Button onClick={onRetry}>{copy.errors.tryAgain}</Button>
        <Button variant="secondary" onClick={onEditText}>
          {copy.errors.editText}
        </Button>
      </div>
    </div>
  );
}

export function errorMessage(code: ErrorCode, limits: { minChars: number; maxChars: number }): string {
  switch (code) {
    case "TEXT_TOO_LONG":
    case "BODY_TOO_LARGE":
      return copy.errors.TEXT_TOO_LONG(num(limits.maxChars));
    case "TEXT_TOO_SHORT":
      return copy.errors.TEXT_TOO_SHORT(num(limits.minChars));
    case "BUSY":
      return copy.errors.BUSY;
    case "LLM_QUOTA":
      return copy.errors.LLM_QUOTA;
    case "LLM_OVERLOADED":
      return copy.errors.LLM_OVERLOADED;
    case "LLM_ERROR":
      return copy.errors.LLM_ERROR;
    case "NETWORK":
      return copy.errors.NETWORK;
    case "INVALID_REQUEST":
      return copy.errors.INVALID_REQUEST;
    default:
      return copy.errors.INTERNAL;
  }
}
