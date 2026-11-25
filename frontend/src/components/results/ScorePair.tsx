import { useEffect, useState } from "react";

import type { Scores } from "../../api/client";
import { copy } from "../../lib/copy";

/**
 * Section 7.4 C2. Two equal blocks, always side by side, never combined into one number.
 *
 * What is deliberately absent (section 9): bands, grades, traffic lights, a threshold that
 * turns a score "red", emoji, and any single combined score. The only colour is the Risk fill,
 * and it is the same red at 10 as at 90, because the product does not judge the number.
 */
export function ScorePair({ scores }: { scores: Scores }) {
  // The authored moment (section 8.6): the bars fill from 0 once, Quality 80ms after Risk. The
  // numbers appear immediately, because a counting ticker would be decoration.
  const [filled, setFilled] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setFilled(true));
    return () => cancelAnimationFrame(id);
  }, []);

  return (
    <section aria-labelledby="scores-heading" className="border-t-2 border-rule-strong pt-8">
      <h2 className="sr-only" id="scores-heading">
        Scores
      </h2>
      <div className="grid gap-8 sm:grid-cols-2 sm:gap-10">
        <ScoreBlock
          label={copy.scores.risk}
          display={scores.risk_index_display}
          exact={scores.risk_index}
          direction={copy.scores.riskDirection}
          fill="var(--signal)"
          filled={filled}
          delayMs={0}
        />
        <ScoreBlock
          label={copy.scores.quality}
          display={scores.disclosure_quality_display}
          exact={scores.disclosure_quality}
          direction={copy.scores.qualityDirection}
          fill="var(--ink)"
          filled={filled}
          delayMs={80}
        />
      </div>

      <p className="t-body mt-8 text-ink-2">
        <strong style={{ fontWeight: 700 }}>
          {copy.scores.notStatedCount(scores.n_not_stated, scores.n_applicable)}
        </strong>{" "}
        {copy.scores.notStatedRest} {copy.scores.readTogether}
      </p>
    </section>
  );
}

function ScoreBlock({
  label, display, exact, direction, fill, filled, delayMs,
}: {
  label: string;
  display: number;
  exact: number;
  direction: string;
  fill: string;
  filled: boolean;
  delayMs: number;
}) {
  return (
    <div>
      <h3 className="t-h3">{label}</h3>
      <p className="mt-2 flex items-baseline gap-2">
        {/* The rounded number is what is read out; the exact value is available for anyone who
            wants it, without putting four decimals on screen. */}
        <span className="t-score" title={`${exact}`}>
          {display}
        </span>
        <span className="t-small text-ink-3">/100</span>
      </p>
      <div
        className="mt-3 h-2 w-full"
        style={{ background: "var(--rule)" }}
        role="img"
        aria-label={`${label}: ${display} out of 100.`}
      >
        <div
          className="h-full"
          style={{
            width: `${filled ? display : 0}%`,
            background: fill,
            transition: `width var(--dur-reveal) var(--ease-out) ${delayMs}ms`,
          }}
        />
      </div>
      <p className="t-small mt-3 max-w-[32ch] text-ink-2">{direction}</p>
    </div>
  );
}
