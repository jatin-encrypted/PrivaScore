import type { Evidence } from "../../api/client";
import { copy } from "../../lib/copy";

/**
 * Section 7.4 C4. The quote marks sit OUTSIDE the span; inside is the exact text the backend
 * sent, which is the policy's own characters (text[start:end]), never the model's quote string
 * and never trimmed, re-cased or "fixed".
 *
 * Quotes that failed verification are not here at all: the backend only sends their count.
 */
export function EvidenceQuote({
  evidence,
  onShowInPolicy,
}: {
  evidence: Evidence;
  onShowInPolicy: () => void;
}) {
  return (
    <li className="border-l-2 border-rule pl-4">
      <p className="t-quote">
        <span aria-hidden="true">&ldquo;</span>
        {evidence.text}
        <span aria-hidden="true">&rdquo;</span>
      </p>
      <p className="t-small mt-1 flex flex-wrap items-baseline gap-x-2 text-ink-3">
        <span className="t-code">{evidence.sentence_id}</span>
        {evidence.heading ? <span>· {evidence.heading}</span> : null}
        <span aria-hidden="true">·</span>
        <button
          type="button"
          onClick={onShowInPolicy}
          className="underline decoration-1 underline-offset-[3px] hover:decoration-2"
        >
          {copy.flagRow.showInPolicy} <span aria-hidden="true">&rarr;</span>
          <span className="sr-only"> ({evidence.sentence_id})</span>
        </button>
      </p>
    </li>
  );
}
