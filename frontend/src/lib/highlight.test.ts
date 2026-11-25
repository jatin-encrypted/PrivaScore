import { describe, expect, it } from "vitest";

import type { EvaluateResponse } from "../api/client";
import { evidenceRanges, highlight } from "./highlight";

type Paragraphs = EvaluateResponse["document"]["paragraphs"];

/** Builds the paragraph list the way the backend does: UTF-16 ranges over the same string. */
function paras(text: string): Paragraphs {
  const out: Paragraphs = [];
  let pos = 0;
  let n = 0;
  for (const line of text.split("\n")) {
    if (line.trim()) {
      n += 1;
      out.push({
        id: `p${String(n).padStart(3, "0")}`,
        offset_utf16: [pos, pos + line.length],
        is_heading: false,
      });
    }
    pos += line.length + 1;
  }
  return out;
}

const marked = (segs: { text: string; flags: string[] }[]) => segs.filter((s) => s.flags.length > 0);
const joined = (segs: { text: string }[]) => segs.map((s) => s.text).join("");

describe("highlight", () => {
  it("returns the paragraph untouched when there is no evidence", () => {
    const text = "First line.\nSecond line.";
    const out = highlight(text, paras(text), []);
    expect(out).toHaveLength(2);
    expect(out[0]!.segments).toEqual([{ text: "First line.", flags: [], sids: [] }]);
  });

  it("splits a paragraph into before, quote and after", () => {
    const text = "We may share data with partners.";
    const out = highlight(text, paras(text), [{ start: 7, end: 17, flag: "G2", sid: "p001.s1" }]);
    expect(out[0]!.segments).toEqual([
      { text: "We may ", flags: [], sids: [] },
      { text: "share data", flags: ["G2"], sids: ["p001.s1"] },
      { text: " with partners.", flags: [], sids: [] },
    ]);
  });

  it("never loses or duplicates a character", () => {
    const text = "Sentence one here. Sentence two here. Sentence three.";
    const out = highlight(text, paras(text), [
      { start: 0, end: 18, flag: "G1", sid: "p001.s1" },
      { start: 19, end: 37, flag: "G2", sid: "p001.s1" },
    ]);
    expect(joined(out[0]!.segments)).toBe(text);
  });

  it("merges two flags citing the same sentence into one segment", () => {
    const text = "We sell personal data for advertising.";
    const out = highlight(text, paras(text), [
      { start: 0, end: 37, flag: "G2", sid: "p001.s1" },
      { start: 0, end: 37, flag: "AI4", sid: "p001.s1" },
    ]);
    expect(marked(out[0]!.segments)).toEqual([
      { text: "We sell personal data for advertising", flags: ["G2", "AI4"], sids: ["p001.s1"] },
    ]);
  });

  it("handles partly overlapping ranges from two flags", () => {
    //            0123456789
    const text = "ABCDEFGHIJ";
    const out = highlight(text, paras(text), [
      { start: 0, end: 6, flag: "G1", sid: "p001.s1" },
      { start: 3, end: 9, flag: "G2", sid: "p001.s1" },
    ]);
    expect(out[0]!.segments).toEqual([
      { text: "ABC", flags: ["G1"], sids: ["p001.s1"] },
      { text: "DEF", flags: ["G1", "G2"], sids: ["p001.s1"] },
      { text: "GHI", flags: ["G2"], sids: ["p001.s1"] },
      { text: "J", flags: [], sids: [] },
    ]);
    expect(joined(out[0]!.segments)).toBe(text);
  });

  it("clips a range that crosses a paragraph boundary", () => {
    const text = "First line.\nSecond line.";
    // 0..24 spans both paragraphs and the newline between them.
    const out = highlight(text, paras(text), [{ start: 0, end: 24, flag: "G1", sid: "p001.s1" }]);
    expect(out[0]!.segments).toEqual([{ text: "First line.", flags: ["G1"], sids: ["p001.s1"] }]);
    expect(out[1]!.segments).toEqual([{ text: "Second line.", flags: ["G1"], sids: ["p001.s1"] }]);
    // The newline itself belongs to no paragraph and is not rendered twice.
    expect(joined(out.flatMap((p) => p.segments))).toBe("First line.Second line.");
  });

  it("keeps offsets correct when an emoji precedes the quote", () => {
    // A surrogate pair is TWO UTF-16 units, which is what the backend's offsets count.
    const text = "😀 We share data with partners.";
    const out = highlight(text, paras(text), [{ start: 6, end: 16, flag: "G2", sid: "p001.s1" }]);
    expect(marked(out[0]!.segments)).toEqual([{ text: "share data", flags: ["G2"], sids: ["p001.s1"] }]);
    expect(joined(out[0]!.segments)).toBe(text);
  });

  it("keeps offsets correct when the emoji is inside the quoted sentence", () => {
    const text = "We 😀 share data.";
    const out = highlight(text, paras(text), [{ start: 0, end: 11, flag: "G2", sid: "p001.s1" }]);
    expect(marked(out[0]!.segments)[0]!.text).toBe("We 😀 share");
  });

  it("ignores an empty range rather than emitting a zero-length segment", () => {
    const text = "Nothing to mark here.";
    const out = highlight(text, paras(text), [{ start: 5, end: 5, flag: "G1", sid: "p001.s1" }]);
    expect(out[0]!.segments).toEqual([{ text, flags: [], sids: [] }]);
  });

  it("marks a quote that is the whole paragraph", () => {
    const text = "Exactly one sentence.";
    const out = highlight(text, paras(text), [{ start: 0, end: 21, flag: "G1", sid: "p001.s1" }]);
    expect(out[0]!.segments).toEqual([{ text, flags: ["G1"], sids: ["p001.s1"] }]);
  });

  it("handles evidence given out of document order", () => {
    const text = "AAAA BBBB CCCC";
    const out = highlight(text, paras(text), [
      { start: 10, end: 14, flag: "G3", sid: "p001.s1" },
      { start: 0, end: 4, flag: "G1", sid: "p001.s1" },
    ]);
    expect(out[0]!.segments.map((s) => s.flags.join(""))).toEqual(["G1", "", "G3"]);
  });

  it("renders a 200k character document in well under 100ms", () => {
    const line = "We may share your personal data with selected third party partners. ";
    const text = Array.from({ length: 3000 }, () => line).join("\n");
    const p = paras(text);
    // One quote in every tenth paragraph, as a real policy produces.
    const ranges = p
      .filter((_, i) => i % 10 === 0)
      .map((par, i) => ({ start: par.offset_utf16[0] + 7, end: par.offset_utf16[0] + 30, flag: `G${i % 7}`, sid: `p${i}.s1` }));
    expect(text.length).toBeGreaterThan(190_000);

    const t0 = performance.now();
    const out = highlight(text, p, ranges);
    const ms = performance.now() - t0;

    expect(out).toHaveLength(3000);
    expect(ms).toBeLessThan(100);
  });
});

describe("evidenceRanges", () => {
  it("tags every quote with the flag that cited it and drops empty ones", () => {
    const flags = [
      { id: "G1", evidence: [{ offset_utf16: [0, 5], sentence_id: "p001.s1" },
                             { offset_utf16: [9, 9], sentence_id: "p001.s2" }] },
      { id: "G2", evidence: [{ offset_utf16: [10, 20], sentence_id: "p002.s1" }] },
    ] as unknown as EvaluateResponse["flags"];
    expect(evidenceRanges(flags)).toEqual([
      { start: 0, end: 5, flag: "G1", sid: "p001.s1" },
      { start: 10, end: 20, flag: "G2", sid: "p002.s1" },
    ]);
  });
});
