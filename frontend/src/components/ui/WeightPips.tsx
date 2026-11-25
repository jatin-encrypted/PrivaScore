import { copy } from "../../lib/copy";

/**
 * Up to three small squares. Weight is how much a flag moves the Risk Index, so a weight-0 flag
 * (DPDP4) shows the "not scored" wording instead of an empty row of pips.
 */
const MAX = 3;

export function WeightPips({ weight, applicable }: { weight: number; applicable: boolean }) {
  if (weight === 0 || !applicable) {
    return <span className="t-small text-ink-3">{copy.riskMarks.notScored}</span>;
  }
  const filled = Math.round(weight);
  return (
    <span className="inline-flex items-center gap-1" title={`Weight ${filled} of ${MAX}`}>
      <span className="sr-only">{`Weight ${filled} of ${MAX}.`}</span>
      {Array.from({ length: MAX }, (_, i) => (
        <span
          key={i}
          aria-hidden="true"
          className="inline-block size-[6px]"
          style={{ background: i < filled ? "var(--ink-2)" : "var(--rule)" }}
        />
      ))}
    </span>
  );
}
