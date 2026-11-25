import type { RiskLevel } from "../../lib/flags";
import { RISK_LABELS } from "../../lib/flags";

/**
 * A 14px square whose FORM, not just its colour, carries the meaning: solid, hatched, dashed,
 * outlined or dotted (section 7.4 C4). Colour is never the only signal, and the label is always
 * present as visually-hidden text so a screen reader and the legend agree.
 */
const STYLES: Record<RiskLevel, React.CSSProperties> = {
  adds: { background: "var(--signal)", border: "2px solid var(--signal)" },
  partly: {
    background:
      "repeating-linear-gradient(135deg, var(--signal) 0 2px, transparent 2px 5px)",
    border: "2px solid var(--signal)",
  },
  none: { border: "2px solid var(--ink)" },
  not_stated: { border: "2px dashed var(--ink-3)" },
  not_scored: { border: "2px dotted var(--rule)" },
};

export function RiskMark({ level }: { level: RiskLevel }) {
  return (
    <>
      <span aria-hidden="true" className="inline-block size-[14px] shrink-0" style={STYLES[level]} />
      <span className="sr-only">{RISK_LABELS[level]}.</span>
    </>
  );
}

export function RiskLegend({ levels }: { levels: RiskLevel[] }) {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-2">
      {levels.map((level) => (
        <li key={level} className="flex items-center gap-2">
          <span aria-hidden="true" className="inline-block size-[14px] shrink-0" style={STYLES[level]} />
          <span className="t-small text-ink-2">{RISK_LABELS[level]}</span>
        </li>
      ))}
    </ul>
  );
}
