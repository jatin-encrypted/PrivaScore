import type { FlagResult } from "../../api/client";
import { stateLabel } from "../../lib/flags";

/** Text only, in --ink-2. No pill, no colour per state: the risk mark carries the direction. */
export function StateTag({ flag }: { flag: Pick<FlagResult, "state" | "status"> }) {
  return <span className="t-small whitespace-nowrap text-ink-2">{stateLabel(flag)}</span>;
}
