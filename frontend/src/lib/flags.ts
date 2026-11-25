/**
 * The single place that turns a flag's API fields into UI labels (section 7.5).
 *
 * The important rule: the risk mark is computed from risk_points / max_risk_points, never from
 * the state. Exposure flags and protective flags read the same state in opposite directions
 * (appendix A: for G4, ED means "a concrete retention period", the most protective answer), so
 * a fixed colour per state would be actively misleading.
 */
import type { FlagResult } from "../api/client";
import { copy } from "./copy";

export type RiskLevel = "adds" | "partly" | "none" | "not_stated" | "not_scored";

export function riskLevel(flag: Pick<FlagResult, "applicable" | "risk_points" | "max_risk_points" | "state">): RiskLevel {
  // Not applicable means excluded from both denominators, so max_risk_points is 0 and a ratio
  // would be a division by zero. DPDP4 (weight 0) and AI2 (when AI1 is not ED/CD) land here.
  if (!flag.applicable || flag.max_risk_points === 0) return "not_scored";
  const ratio = flag.risk_points / flag.max_risk_points;
  // scoring.py only ever produces 0, 0.5 or 1 times the weight, but compare with tolerance
  // rather than equality so a float never falls through to the wrong label.
  if (ratio >= 0.99) return "adds";
  if (ratio > 0.01) return "partly";
  return flag.state === "NS" ? "not_stated" : "none";
}

export const RISK_LABELS: Record<RiskLevel, string> = {
  adds: copy.riskMarks.adds,
  partly: copy.riskMarks.partly,
  none: copy.riskMarks.none,
  not_stated: copy.riskMarks.notStated,
  not_scored: copy.riskMarks.notScored,
};

/** A rejected flag is scored as UN, but its tag says so plainly rather than claiming a label. */
export function stateLabel(flag: Pick<FlagResult, "state" | "status">): string {
  if (flag.status === "rejected") return "Unverified";
  return copy.states[flag.state];
}

/** The status line under the evidence (exact wording from section 7.6). */
export function statusText(flag: Pick<FlagResult, "status" | "dropped_evidence_count" | "n_candidates" | "n_search_terms">): string {
  switch (flag.status) {
    case "verified":
      return copy.status.verified;
    case "verified_partial":
      return copy.status.verified_partial(flag.dropped_evidence_count);
    case "absent_unverifiable":
      return copy.status.absent_unverifiable(flag.n_candidates);
    case "no_candidates":
      return copy.status.no_candidates(flag.n_search_terms);
    case "not_applicable":
      return copy.status.not_applicable;
    case "rejected":
      return copy.status.rejected;
  }
}

export type GroupId = "general" | "ai" | "dpdp";
export const GROUP_ORDER: GroupId[] = ["general", "ai", "dpdp"];

/** Groups in a fixed order, each keeping the pipeline's flag order. */
export function byGroup(flags: FlagResult[]): { id: GroupId; title: string; flags: FlagResult[] }[] {
  return GROUP_ORDER.map((id) => ({
    id,
    title: copy.groups[id],
    flags: flags.filter((f) => f.group === id),
  })).filter((g) => g.flags.length > 0);
}

/**
 * Appendix C. The OPP-115 names are what the API sends and what the literature uses, so both
 * are shown: the display name as the label, the original as secondary text.
 */
export const CATEGORY_DISPLAY: Record<string, string> = {
  "First Party Collection/Use": "Data the company collects and uses",
  "Third Party Sharing/Collection": "Sharing with third parties",
  "User Choice/Control": "User choices and controls",
  "User Access, Edit and Deletion": "Access, editing and deletion",
  "Data Retention": "How long data is kept",
  "Data Security": "Security",
  "Policy Change": "Changes to the policy",
  "Do Not Track": "Do Not Track",
  "International and Specific Audiences": "International users, children and other groups",
  Other: "Other (introductions, contact details, general text)",
};

export const categoryDisplay = (name: string): string => CATEGORY_DISPLAY[name] ?? name;

/** "Other" is pinned last and dimmed: it is the catch-all, not a finding (section 7.4 C6). */
export function sortedCategories<T extends { name: string; share: number }>(categories: T[]): T[] {
  const rest = categories.filter((c) => c.name !== "Other").sort((a, b) => b.share - a.share);
  const other = categories.filter((c) => c.name === "Other");
  return [...rest, ...other];
}
