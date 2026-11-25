import type { FlagResult } from "../../api/client";
import { copy } from "../../lib/copy";
import { byGroup } from "../../lib/flags";
import { RiskLegend } from "../ui/RiskMark";
import { FlagRow } from "./FlagRow";

/**
 * Section 7.4 C4. Three groups with plain headings, each in the pipeline's flag order, so the
 * list is identical for every policy and two results can be read side by side.
 */
export function FlagGroups({
  flags,
  onShowInPolicy,
}: {
  flags: FlagResult[];
  onShowInPolicy: (sentenceId: string) => void;
}) {
  return (
    <section aria-labelledby="flags-heading">
      <h2 className="t-h2 border-t-2 border-rule-strong pt-8" id="flags-heading">
        {copy.results.flagsHeading}
      </h2>

      <div className="mt-6">
        <RiskLegend levels={["adds", "partly", "none", "not_stated", "not_scored"]} />
      </div>

      {byGroup(flags).map((group) => (
        <div key={group.id} className="mt-10">
          <h3 className="t-h3">{group.title}</h3>
          <div className="mt-3">
            {group.flags.map((flag) => (
              <FlagRow key={flag.id} flag={flag} onShowInPolicy={onShowInPolicy} />
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
