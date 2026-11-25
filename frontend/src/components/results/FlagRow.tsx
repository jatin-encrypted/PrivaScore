import { useId, useState } from "react";
import { CaretDown } from "@phosphor-icons/react";

import type { FlagResult } from "../../api/client";
import { copy } from "../../lib/copy";
import { riskLevel, stateLabel, statusText } from "../../lib/flags";
import { RiskMark } from "../ui/RiskMark";
import { StateTag } from "../ui/StateTag";
import { WeightPips } from "../ui/WeightPips";
import { EvidenceQuote } from "./EvidenceQuote";

/**
 * Section 7.4 C4. A row is a button that expands in place. Expanded it shows, in order: the
 * question, what this state means FOR THIS FLAG (verbatim from flag_rules.json), the model's
 * rationale labelled as such, the verified quotes, the status line, and the points.
 *
 * The rationale is labelled "Why:" and attributed, because it is the model's reasoning and not
 * a finding the pipeline verified (section 9).
 */
export function FlagRow({
  flag,
  onShowInPolicy,
}: {
  flag: FlagResult;
  onShowInPolicy: (sentenceId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const level = riskLevel(flag);

  return (
    <div className="border-b border-rule">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 py-3 text-left"
      >
        <RiskMark level={level} />
        <span className="t-code w-12 shrink-0">{flag.id}</span>
        <span className="t-row-title min-w-0 flex-1">{flag.title}</span>
        <StateTag flag={flag} />
        <span className="hidden sm:block">
          <WeightPips weight={flag.weight} applicable={flag.applicable} />
        </span>
        <CaretDown
          aria-hidden="true"
          size={20}
          className="shrink-0 transition-transform duration-[220ms]"
          style={{ transform: open ? "rotate(180deg)" : "none" }}
        />
      </button>

      {/* grid-template-rows 0fr -> 1fr animates height without measuring it (section 8.6). */}
      <div
        id={panelId}
        hidden={!open}
        className="grid overflow-hidden"
        style={{ gridTemplateRows: open ? "1fr" : "0fr", transition: "grid-template-rows var(--dur-base) var(--ease-out)" }}
      >
        {/* Indented to line up with the row title (mark 14px + gap 12 + id 48 + gap 12), so the
            panel reads as this flag's content and not as a sibling of the rows. */}
        <div className="min-h-0 pb-6 pl-[26px] sm:pl-[86px]">
          <p className="t-body text-ink-2">{flag.question}</p>

          <p className="t-body mt-4">
            <span style={{ fontWeight: 650 }}>{copy.flagRow.meaning(stateLabel(flag))}</span>{" "}
            <span className="text-ink-2">{flag.state_meaning}</span>
          </p>

          {flag.rationale ? (
            <p className="t-body mt-4">
              <span style={{ fontWeight: 650 }}>{copy.flagRow.rationale}</span>{" "}
              <span className="text-ink-2">{flag.rationale}</span>
            </p>
          ) : null}

          {flag.evidence.length > 0 ? (
            <>
              <h4 className="t-small mt-6 text-ink">{copy.flagRow.evidence(flag.evidence.length)}</h4>
              <ul className="mt-3 space-y-4">
                {flag.evidence.map((e) => (
                  <EvidenceQuote
                    key={`${e.sentence_id}-${e.offset_utf16[0]}`}
                    evidence={e}
                    onShowInPolicy={() => onShowInPolicy(e.sentence_id)}
                  />
                ))}
              </ul>
            </>
          ) : null}

          <p className="t-small mt-6 text-ink-2">
            {statusText(flag)}
            {flag.dropped_evidence_count > 0 && flag.status !== "verified_partial"
              ? ` ${copy.flagRow.dropped(flag.dropped_evidence_count)}`
              : null}
          </p>

          <p className="t-small t-num mt-3 text-ink-3">
            {flag.weight === 0
              ? copy.flagRow.informational
              : copy.flagRow.points(flag.risk_points, flag.max_risk_points, flag.quality_points, flag.weight)}
          </p>
        </div>
      </div>
    </div>
  );
}
