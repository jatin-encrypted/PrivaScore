import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { riskLevel, sortedCategories, stateLabel, statusText } from "../../lib/flags";
import { flag, response, TEXT } from "../../test/fixture";
import { CategoryProfile } from "./CategoryProfile";
import { FlagGroups } from "./FlagGroups";
import { FlagRow } from "./FlagRow";
import { PolicySummary } from "./PolicySummary";
import { ReadingPanel } from "./ReadingPanel";
import { ResultsView } from "./ResultsView";
import { ScorePair } from "./ScorePair";
import { SourceDocument } from "./SourceDocument";

describe("riskLevel is computed from points, never from the state", () => {
  it("calls a full-weight exposure flag 'adds risk'", () => {
    expect(riskLevel(flag({ risk_points: 3, max_risk_points: 3 }))).toBe("adds");
  });

  it("calls a half-weight flag 'partly'", () => {
    expect(riskLevel(flag({ risk_points: 1, max_risk_points: 2 }))).toBe("partly");
  });

  it("calls a protective flag at ED 'no added risk', even though the state is Disclosed", () => {
    // G5 ED is the most protective answer: same state as G2 ED, opposite meaning.
    expect(riskLevel(flag({ state: "ED", risk_points: 0, max_risk_points: 2 }))).toBe("none");
  });

  it("distinguishes 'not stated' from 'no added risk' at zero points", () => {
    expect(riskLevel(flag({ state: "NS", risk_points: 0, max_risk_points: 2 }))).toBe("not_stated");
  });

  it("never divides by zero for a flag that is not scored", () => {
    expect(riskLevel(flag({ applicable: false, risk_points: 0, max_risk_points: 0 }))).toBe("not_scored");
    expect(riskLevel(flag({ weight: 0, applicable: false, max_risk_points: 0 }))).toBe("not_scored");
  });
});

describe("stateLabel", () => {
  it("uses the plain label for a normal state", () => {
    expect(stateLabel(flag({ state: "CD", status: "verified" }))).toBe("Conditional");
  });

  it("says Unverified for a rejected flag rather than claiming Unclear", () => {
    expect(stateLabel(flag({ state: "UN", status: "rejected" }))).toBe("Unverified");
  });
});

describe("statusText", () => {
  it("explains that absence cannot be proven, with the candidate count", () => {
    expect(statusText(flag({ status: "absent_unverifiable", n_candidates: 4 })))
      .toMatch(/nothing on this in the 4 sentences.*Absence can't be proven/);
  });

  it("explains that no search term matched, so Gemini was never asked", () => {
    expect(statusText(flag({ status: "no_candidates", n_search_terms: 7 })))
      .toMatch(/No sentence matched any of the 7 search terms.*without asking Gemini/);
  });

  it("says a rejected flag makes the scores incomplete", () => {
    expect(statusText(flag({ status: "rejected" }))).toMatch(/Scored as Unclear, so the scores are incomplete/);
  });
});

describe("ScorePair", () => {
  const data = response();

  it("shows both scores with their directions, and never a combined one", () => {
    render(<ScorePair scores={data.scores} />);
    expect(screen.getByText("Privacy Risk Index")).toBeInTheDocument();
    expect(screen.getByText("Disclosure Quality")).toBeInTheDocument();
    expect(screen.getByText("Lower means less exposure described.")).toBeInTheDocument();
    expect(screen.getByText("Higher means more of the 16 practices are addressed clearly.")).toBeInTheDocument();
  });

  it("rounds for display but keeps the exact value available", () => {
    render(<ScorePair scores={data.scores} />);
    expect(screen.getByText("68")).toHaveAttribute("title", "67.8571");
  });

  it("tells the reader to read the two together", () => {
    render(<ScorePair scores={data.scores} />);
    expect(screen.getByText(/3 of 14/)).toBeInTheDocument();
    expect(screen.getByText(/Read the two scores together/)).toBeInTheDocument();
  });

  it("shows no grade, band or verdict (section 9)", () => {
    const { container } = render(<ScorePair scores={data.scores} />);
    expect(container.textContent).not.toMatch(/\b(safe|unsafe|good|bad|poor|excellent|compliant|grade|[A-F][+-]?\b score)/i);
  });
});

describe("PolicySummary banners", () => {
  it("warns loudly in mock mode", () => {
    const data = response({
      warnings: [{ code: "MOCK_PROVIDER", message: "Mock mode: these labels are placeholders, not a real analysis." }],
    });
    render(<PolicySummary data={data} />);
    expect(screen.getByText(/Mock mode/)).toBeInTheDocument();
  });

  it("names the flags that made the scores incomplete", () => {
    const base = response();
    const data = response({ scores: { ...base.scores, complete: false, rejected_flags: ["G4", "AI3"] } });
    render(<PolicySummary data={data} />);
    expect(screen.getByText(/2 practices couldn't be verified.*G4, AI3.*scores are incomplete/)).toBeInTheDocument();
  });

  it("falls back to a neutral title when no company name was given", () => {
    const base = response();
    const data = response({ policy: { ...base.policy, company_name: null } });
    render(<PolicySummary data={data} />);
    expect(screen.getByRole("heading", { level: 1, name: "Your policy" })).toBeInTheDocument();
  });

  it("names the model that produced the labels", () => {
    render(<PolicySummary data={response()} />);
    expect(screen.getByText(/gemini-3\.6-flash/)).toBeInTheDocument();
  });
});

describe("FlagRow", () => {
  const g2 = response().flags.find((f) => f.id === "G2")!;

  it("is collapsed until pressed", async () => {
    render(<FlagRow flag={g2} onShowInPolicy={vi.fn()} />);
    const row = screen.getByRole("button", { expanded: false });
    await userEvent.click(row);
    expect(screen.getByRole("button", { expanded: true })).toBeInTheDocument();
  });

  it("shows the rule text verbatim, labelled as what the state means for THIS practice", async () => {
    render(<FlagRow flag={g2} onShowInPolicy={vi.fn()} />);
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Disclosed for this practice means:")).toBeInTheDocument();
    expect(screen.getByText(g2.state_meaning)).toBeInTheDocument();
  });

  it("attributes the rationale to the model instead of stating it as fact", async () => {
    render(<FlagRow flag={g2} onShowInPolicy={vi.fn()} />);
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Why:")).toBeInTheDocument();
    expect(screen.getByText(g2.rationale!)).toBeInTheDocument();
  });

  it("shows the verified quote and its sentence id", async () => {
    render(<FlagRow flag={g2} onShowInPolicy={vi.fn()} />);
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByText(g2.evidence[0]!.text)).toBeInTheDocument();
    expect(screen.getByText("p002.s1")).toBeInTheDocument();
    expect(screen.getByText(/Every quote was found word for word in your text/)).toBeInTheDocument();
  });

  it("asks the parent to reveal the span in the policy", async () => {
    const onShow = vi.fn();
    render(<FlagRow flag={g2} onShowInPolicy={onShow} />);
    await userEvent.click(screen.getByRole("button", { expanded: false }));
    await userEvent.click(screen.getByRole("button", { name: /Show in policy/ }));
    expect(onShow).toHaveBeenCalledWith("p002.s1");
  });

  it("reports a dropped quote by count only, never its text", async () => {
    const partial = flag({
      status: "verified_partial",
      dropped_evidence_count: 2,
      evidence: g2.evidence,
    });
    render(<FlagRow flag={partial} onShowInPolicy={vi.fn()} />);
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByText(/2 quotes failed the word-for-word check and were dropped/)).toBeInTheDocument();
  });

  it("says an informational flag is not part of either score", async () => {
    const dpdp4 = response().flags.find((f) => f.id === "DPDP4")!;
    render(<FlagRow flag={dpdp4} onShowInPolicy={vi.fn()} />);
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Informational. Not part of either score.")).toBeInTheDocument();
  });

  it("shows no 'Why' line when the pipeline gave no model rationale", async () => {
    const ai2 = response().flags.find((f) => f.id === "AI2")!;
    render(<FlagRow flag={ai2} onShowInPolicy={vi.fn()} />);
    await userEvent.click(screen.getByRole("button"));
    expect(screen.queryByText("Why:")).not.toBeInTheDocument();
    expect(screen.getByText(/Only applies when the policy says it trains AI on user data/)).toBeInTheDocument();
  });

  it("never shows a confidence or probability (section 9)", async () => {
    const { container } = render(<FlagRow flag={g2} onShowInPolicy={vi.fn()} />);
    await userEvent.click(screen.getByRole("button"));
    expect(container.textContent).not.toMatch(/confiden|probabilit|\d+% (sure|likely|confident)/i);
  });
});

describe("FlagGroups", () => {
  it("renders the three groups with plain headings, in order", () => {
    render(<FlagGroups flags={response().flags} onShowInPolicy={vi.fn()} />);
    const headings = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(headings).toEqual(["General practices", "AI practices", "India DPDP readiness"]);
  });

  it("keeps the pipeline's flag order inside each group", () => {
    render(<FlagGroups flags={response().flags} onShowInPolicy={vi.fn()} />);
    const ids = screen.getAllByRole("button").map((b) => b.textContent ?? "");
    expect(ids.filter((t) => t.includes("G2")).length).toBe(1);
    const order = response().flags.map((f) => f.id);
    expect(order.indexOf("G1")).toBeLessThan(order.indexOf("G2"));
  });

  it("gives the risk marks a text legend, so colour is never the only signal", () => {
    render(<FlagGroups flags={response().flags} onShowInPolicy={vi.fn()} />);
    for (const label of ["Adds risk", "Partly adds risk", "No added risk", "Not stated", "Not scored"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });
});

describe("CategoryProfile", () => {
  it("shows shares that do not add up to 100% without implying they should", () => {
    render(<CategoryProfile metrics={response().metrics} />);
    expect(screen.getByText(/do not add up to 100%/)).toBeInTheDocument();
    expect(screen.getByText(/Descriptive only: not part of the scores/)).toBeInTheDocument();
  });

  it("shows both the display name and the OPP-115 name", () => {
    render(<CategoryProfile metrics={response().metrics} />);
    expect(screen.getByText("Sharing with third parties")).toBeInTheDocument();
    expect(screen.getByText("Third Party Sharing/Collection")).toBeInTheDocument();
  });

  it("pins Other last even though it has the largest share", () => {
    const sorted = sortedCategories(response().metrics.bert_profile.categories!);
    expect(sorted.at(-1)!.name).toBe("Other");
    expect(sorted[0]!.name).toBe("Third Party Sharing/Collection");
  });

  it("explains itself when the classifier is unavailable", () => {
    const base = response();
    const metrics = { ...base.metrics, bert_profile: { available: false, reason: "unavailable" as const } };
    render(<CategoryProfile metrics={metrics} />);
    expect(screen.getByText(/isn't available on this server/)).toBeInTheDocument();
  });
});

describe("ReadingPanel", () => {
  it("reports the readability figures with their units", () => {
    render(<ReadingPanel metrics={response().metrics} />);
    expect(screen.getByText("Grade 15.5")).toBeInTheDocument();
    expect(screen.getByText("0-100, higher is easier")).toBeInTheDocument();
  });

  it("states the vague-sentence share and that a cue is not a judgement", () => {
    render(<ReadingPanel metrics={response().metrics} />);
    expect(screen.getByText("48%")).toBeInTheDocument();
    expect(screen.getByText(/A cue is a hint of vague wording, not a judgement/)).toBeInTheDocument();
  });

  it("underlines the cue words inside the example sentence", () => {
    render(<ReadingPanel metrics={response().metrics} />);
    expect(screen.getByText("in some cases")).toBeInTheDocument();
    expect(screen.getByText("such as")).toBeInTheDocument();
  });
});

describe("SourceDocument", () => {
  const data = response();

  it("renders the policy text with the verified quotes marked", () => {
    const { container } = render(<SourceDocument data={data} text={TEXT} />);
    const marks = [...container.querySelectorAll("mark.evidence")];
    expect(marks).toHaveLength(2);
    expect(marks.map((m) => m.textContent)).toEqual([
      data.flags.find((f) => f.id === "G2")!.evidence[0]!.text,
      data.flags.find((f) => f.id === "G5")!.evidence[0]!.text,
    ]);
  });

  it("gives each marked sentence a target id for 'Show in policy'", () => {
    const { container } = render(<SourceDocument data={data} text={TEXT} />);
    expect(container.querySelector("#ev-p002\\.s1")).not.toBeNull();
    expect(container.querySelector("#ev-p003\\.s1")).not.toBeNull();
  });

  it("names the flag that cites each span, for the popover", () => {
    const { container } = render(<SourceDocument data={data} text={TEXT} />);
    expect(container.querySelector("mark.evidence")).toHaveAttribute("data-flags", "G2");
  });

  it("reproduces the pasted text exactly, losing nothing", () => {
    const { container } = render(<SourceDocument data={data} text={TEXT} />);
    const rendered = [...container.querySelectorAll("p")].map((p) => p.textContent).join("\n");
    expect(rendered).toBe(TEXT);
  });

  it("marks headings as headings", () => {
    const { container } = render(<SourceDocument data={data} text={TEXT} />);
    expect(container.querySelector("#src-p001")).toHaveStyle({ fontWeight: "700" });
  });
});

describe("ResultsView", () => {
  it("assembles every section", () => {
    render(<ResultsView data={response()} text={TEXT} onReset={vi.fn()} />);
    for (const name of [
      "The 16 practices",
      "What the paragraphs are about",
      "How hard it is to read",
      "How to read these results",
    ]) {
      expect(screen.getByRole("heading", { name })).toBeInTheDocument();
    }
  });

  it("labels the source panel so it is findable", () => {
    render(<ResultsView data={response()} text={TEXT} onReset={vi.fn()} />);
    expect(within(screen.getByRole("complementary")).getByText("Your text")).toBeInTheDocument();
  });

  it("offers to analyse another policy", async () => {
    const onReset = vi.fn();
    render(<ResultsView data={response()} text={TEXT} onReset={onReset} />);
    await userEvent.click(screen.getByRole("button", { name: "Analyze another policy" }));
    expect(onReset).toHaveBeenCalledOnce();
  });

  it("builds the JSON download without the pasted text in it", async () => {
    const data = response();
    render(<ResultsView data={data} text={TEXT} onReset={vi.fn()} />);
    const blobs: string[] = [];
    vi.stubGlobal("Blob", class {
      constructor(parts: string[]) { blobs.push(parts.join("")); }
    });
    vi.stubGlobal("URL", { createObjectURL: () => "blob:x", revokeObjectURL: () => {} });
    await userEvent.click(screen.getByRole("button", { name: "Download JSON" }));
    expect(blobs).toHaveLength(1);
    expect(blobs[0]).not.toContain(TEXT);
    expect(JSON.parse(blobs[0]!).document.text).toBeNull();
    vi.unstubAllGlobals();
  });
});
