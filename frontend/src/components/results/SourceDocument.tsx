import { useMemo } from "react";

import type { EvaluateResponse } from "../../api/client";
import { copy } from "../../lib/copy";
import { evidenceRanges, highlight } from "../../lib/highlight";

/**
 * Section 7.4 C5. The text the user pasted, rendered paragraph by paragraph from the backend's
 * ranges, with every verified quote marked.
 *
 * Segments are React text nodes: never dangerouslySetInnerHTML. This is untrusted pasted text,
 * and the whole point of the panel is that the user can see it unaltered.
 *
 * The heading says "Your text" only when it IS the reader's text. A saved example is a published
 * policy that the reader never pasted, so it is named after its company instead.
 */
export function SourceDocument({ data, text }: { data: EvaluateResponse; text: string }) {
  const paragraphs = useMemo(
    () => highlight(text, data.document.paragraphs, evidenceRanges(data.flags)),
    [text, data],
  );

  return (
    <aside aria-labelledby="source-heading" className="min-w-0">
      <h2 className="t-h3 border-b-2 border-rule-strong pb-2" id="source-heading">
        {data.source === "example" && data.policy.company_name
          ? copy.results.sourceLabelSaved(data.policy.company_name)
          : copy.results.sourceLabel}
      </h2>

      <div className="mt-4 bg-surface p-4">
        {paragraphs.map((p) => (
          <p
            key={p.id}
            id={`src-${p.id}`}
            // content-visibility lets the browser skip layout for off-screen paragraphs, which
            // is what keeps a 200k character policy scrolling smoothly.
            className={`t-body max-w-none ${p.isHeading ? "mt-4 first:mt-0" : "mt-3 first:mt-0"}`}
            style={{ contentVisibility: "auto", containIntrinsicSize: "auto 3rem", fontWeight: p.isHeading ? 700 : undefined }}
          >
            {p.segments.map((seg, i) =>
              seg.flags.length > 0 ? (
                <mark
                  key={i}
                  className="evidence"
                  // The first span of each cited sentence carries its id, which is what
                  // "Show in policy" scrolls to and moves focus onto.
                  id={seg.sids[0] ? `ev-${seg.sids[0]}` : undefined}
                  data-flags={seg.flags.join(" ")}
                  data-sids={seg.sids.join(" ")}
                  tabIndex={-1}
                >
                  {seg.text}
                </mark>
              ) : (
                <span key={i}>{seg.text}</span>
              ),
            )}
          </p>
        ))}
      </div>
    </aside>
  );
}
