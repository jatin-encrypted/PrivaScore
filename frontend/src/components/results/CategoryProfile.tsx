import type { Metrics } from "../../api/client";
import { copy } from "../../lib/copy";
import { categoryDisplay, sortedCategories } from "../../lib/flags";
import { percent } from "../../lib/format";

/**
 * Section 7.4 C6. Horizontal bars, because the classifier is MULTI-LABEL: a paragraph can count
 * toward several categories and the shares do not sum to 100%, which rules out a pie, a donut
 * or a 100% stacked bar (gotcha 11).
 *
 * The probabilities themselves are never shown, only the share of paragraphs at or above 0.5
 * (section 9 forbids presenting a confidence).
 */
export function CategoryProfile({ metrics }: { metrics: Metrics }) {
  const profile = metrics.bert_profile;

  return (
    <section aria-labelledby="bert-heading">
      <h2 className="t-h2 border-t-2 border-rule-strong pt-8" id="bert-heading">
        {copy.results.bertHeading}
      </h2>

      {!profile.available || !profile.categories ? (
        <p className="t-body mt-4 text-ink-2">{copy.results.bertUnavailable}</p>
      ) : (
        <>
          <ul className="mt-6 space-y-3">
            {sortedCategories(profile.categories).map((c) => {
              const other = c.name === "Other";
              return (
                <li key={c.name} className="grid grid-cols-[1fr_auto] items-baseline gap-x-4 sm:grid-cols-[18rem_1fr_4rem]">
                  <span className={`t-small ${other ? "text-ink-3" : "text-ink"}`}>
                    {categoryDisplay(c.name)}
                    <span className="t-code block">{c.name}</span>
                  </span>
                  <span className="order-3 h-2 w-full sm:order-none" style={{ background: "var(--rule)" }}>
                    <span
                      className="block h-full"
                      style={{ width: `${c.share * 100}%`, background: other ? "var(--ink-3)" : "var(--ink-2)" }}
                    />
                  </span>
                  <span className="t-small t-num text-right text-ink-2">{percent(c.share)}</span>
                </li>
              );
            })}
          </ul>
          <p className="t-small mt-6 max-w-[68ch] text-ink-3">{copy.results.bertNote}</p>
        </>
      )}
    </section>
  );
}
