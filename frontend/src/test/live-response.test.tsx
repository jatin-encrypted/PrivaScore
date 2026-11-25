/**
 * Renders a response captured from the running backend, not a hand-written fixture.
 *
 * live-response.json was produced by POSTing gold_set/policies/text/P11_razorpay.txt to
 * /api/v1/evaluate with the mock LLM provider and BERT loaded, so it has the real shapes: 16
 * flags in pipeline order, 75 paragraphs, real UTF-16 offsets and a real category profile.
 * Regenerate it if the response contract changes; the typed import will fail the build if the
 * schema and this file disagree.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { EvaluateResponse } from "../api/client";
import { evidenceRanges, highlight } from "../lib/highlight";
import { ResultsView } from "../components/results/ResultsView";
import live from "./live-response.json";

const text: string = live.text;
const data = live.response as unknown as EvaluateResponse;

describe("a real backend response", () => {
  it("is the shape the generated types describe", () => {
    const typed: EvaluateResponse = data;
    expect(typed.flags).toHaveLength(16);
    expect(typed.api_version).toBe("1");
  });

  it("has offsets that still slice the text back to each quote", () => {
    let n = 0;
    for (const f of data.flags) {
      for (const e of f.evidence) {
        const [a, b] = e.offset_utf16;
        expect(text.slice(a, b)).toBe(e.text);
        n += 1;
      }
    }
    expect(n).toBeGreaterThan(0);
  });

  it("highlights without losing a character of any paragraph", () => {
    const paragraphs = highlight(text, data.document.paragraphs, evidenceRanges(data.flags));
    expect(paragraphs).toHaveLength(data.document.paragraphs.length);
    paragraphs.forEach((p, i) => {
      const [a, b] = data.document.paragraphs[i]!.offset_utf16;
      expect(p.segments.map((s) => s.text).join("")).toBe(text.slice(a, b));
    });
  });

  it("merges the spans two flags cite into one mark, naming both flags", () => {
    // Real data has this: G1 and AI1 both cite p004.s1, and G6 and AI5 both cite p001.s1, so
    // 13 verified quotes become 11 marked spans. Nesting a mark inside a mark instead would
    // double the highlight and lose one of the two flag names.
    const quotes = data.flags.flatMap((f) => f.evidence);
    const distinctSpans = new Set(quotes.map((e) => e.offset_utf16.join("-")));
    expect(quotes.length).toBeGreaterThan(distinctSpans.size);

    const { container } = render(<ResultsView data={data} text={text} onReset={vi.fn()} />);
    const marks = [...container.querySelectorAll("mark.evidence")];
    expect(marks).toHaveLength(distinctSpans.size);

    const shared = marks.filter((m) => (m.getAttribute("data-flags") ?? "").includes(" "));
    expect(shared.length).toBe(quotes.length - distinctSpans.size);
    expect(shared.map((m) => m.getAttribute("data-flags"))).toEqual(
      expect.arrayContaining(["G6 AI5", "G1 AI1"]),
    );
  });

  it("renders every section and all 16 rows", () => {
    render(<ResultsView data={data} text={text} onReset={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Razorpay" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "The 16 practices" })).toBeInTheDocument();
    const rows = screen.getAllByRole("button", { expanded: false });
    expect(rows).toHaveLength(16);
  });

  it("shows the real category profile, whose shares exceed 100% because it is multi-label", () => {
    const shares = data.metrics.bert_profile.categories!.reduce((s, c) => s + c.share, 0);
    expect(shares).toBeGreaterThan(1);
    render(<ResultsView data={data} text={text} onReset={vi.fn()} />);
    expect(screen.getByText(/do not add up to 100%/)).toBeInTheDocument();
  });

  it("reproduces the pasted policy exactly in the source panel", () => {
    const { container } = render(<ResultsView data={data} text={text} onReset={vi.fn()} />);
    const panel = container.querySelector("aside")!;
    const rendered = [...panel.querySelectorAll("p")].map((p) => p.textContent).join("\n");
    const expected = data.document.paragraphs
      .map(({ offset_utf16: [a, b] }) => text.slice(a, b))
      .join("\n");
    expect(rendered).toBe(expected);
  });
});
