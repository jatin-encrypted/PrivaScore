import { useEffect, useState } from "react";

import { copy } from "../lib/copy";
import { countWords, elapsed, num, readingMinutes } from "../lib/format";
import { Button } from "./ui/Button";

const SLOW_MS = 90_000;
const VERY_SLOW_MS = 240_000;

/**
 * Screen B (section 7.4). The request is one blocking call, so the UI does NOT know which step
 * is running: the steps are an explanation list with no checkmarks and no percentage
 * (section 8.8 bans both). The only truthful moving parts are the elapsed timer and the
 * indeterminate bar.
 */
export function AnalysisProgress({
  text,
  startedAt,
  onCancel,
}: {
  text: string;
  startedAt: number;
  onCancel: () => void;
}) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const ms = Math.max(0, now - startedAt);
  const words = countWords(text);

  return (
    <div className="mx-auto max-w-[880px]">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
        <h1 className="t-h2">{copy.loading.title}</h1>
        {/* The timer is real elapsed time. It is deliberately NOT announced: see the single
            aria-live region in App, which says "Analysis started" and "complete" once each. */}
        <p className="t-small t-num text-ink-2" aria-hidden="true">
          {copy.loading.elapsed(elapsed(ms))}
        </p>
      </div>

      <div className="mt-4 loading-track" role="presentation" />
      <p className="t-small loading-static mt-4 text-ink-2">{copy.loading.reducedMotion}</p>

      <p className="t-small t-num mt-6 text-ink-2">
        {copy.loading.size(num(words), num(readingMinutes(text)))}
      </p>

      <h2 className="t-h3 mt-10">{copy.loading.stepsHeading}</h2>
      <ul className="t-body mt-3 space-y-1 text-ink-2">
        {copy.loading.steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ul>

      {ms >= SLOW_MS ? (
        <p className="t-small mt-6 text-ink-2">
          {ms >= VERY_SLOW_MS ? copy.loading.verySlow : copy.loading.slow}
        </p>
      ) : null}

      <div className="mt-10 flex flex-wrap items-center justify-between gap-4 border-t border-rule pt-6">
        <p className="t-small text-ink-3">{copy.loading.footer}</p>
        <Button variant="secondary" onClick={onCancel}>
          {copy.loading.cancel}
        </Button>
      </div>
    </div>
  );
}
