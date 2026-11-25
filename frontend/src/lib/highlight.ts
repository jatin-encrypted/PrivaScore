/**
 * Turns the document's paragraph ranges plus every flag's evidence ranges into per-paragraph
 * render segments (section 7.7).
 *
 * All offsets are UTF-16 code-unit indexes into the exact string that was sent to the backend,
 * which is why the client keeps that normalised string and never re-normalises it.
 *
 * Two flags citing the same sentence is normal, so overlaps are merged by collecting the flag
 * set per segment rather than nesting marks. Segments are plain text nodes: never
 * dangerouslySetInnerHTML, because this is untrusted pasted text.
 */
import type { EvaluateResponse } from "../api/client";

export type Segment = {
  text: string;
  /** Which flags cite this span. Two flags citing one sentence is normal, hence a list. */
  flags: string[];
  /** Which cited sentences this span belongs to, so "Show in policy" can target one. */
  sids: string[];
};
export type HighlightedParagraph = {
  id: string;
  isHeading: boolean;
  segments: Segment[];
};

type Range = { start: number; end: number; flag: string; sid: string };

/** Every verified quote, tagged with the flag that cited it. */
export function evidenceRanges(flags: EvaluateResponse["flags"]): Range[] {
  const out: Range[] = [];
  for (const f of flags) {
    for (const e of f.evidence) {
      const [start, end] = e.offset_utf16;
      if (end > start) out.push({ start, end, flag: f.id, sid: e.sentence_id });
    }
  }
  return out;
}

export function highlight(
  text: string,
  paragraphs: EvaluateResponse["document"]["paragraphs"],
  ranges: Range[],
): HighlightedParagraph[] {
  // Sorting once lets each paragraph scan forward from where the last one stopped, so the whole
  // document is O(n log n) rather than paragraphs x ranges.
  const sorted = [...ranges].sort((a, b) => a.start - b.start || a.end - b.end);
  let cursor = 0;

  return paragraphs.map((p) => {
    const [pStart, pEnd] = p.offset_utf16;
    while (cursor < sorted.length && sorted[cursor]!.end <= pStart) cursor += 1;

    // A quote is clipped to its paragraph: a range that spills past the end (which segmentation
    // should prevent, but the backend is not asked to guarantee it) simply stops there.
    const local: Range[] = [];
    for (let i = cursor; i < sorted.length && sorted[i]!.start < pEnd; i += 1) {
      const r = sorted[i]!;
      const start = Math.max(r.start, pStart);
      const end = Math.min(r.end, pEnd);
      if (end > start) local.push({ start, end, flag: r.flag, sid: r.sid });
    }

    return { id: p.id, isHeading: p.is_heading, segments: cut(text, pStart, pEnd, local) };
  });
}

/**
 * Cuts [start, end) at every range boundary and labels each piece with the flags covering it.
 * Boundaries, not intervals, so overlapping ranges produce one flat list of segments.
 */
function cut(text: string, start: number, end: number, ranges: Range[]): Segment[] {
  if (ranges.length === 0) {
    return start < end ? [{ text: text.slice(start, end), flags: [], sids: [] }] : [];
  }

  const bounds = new Set<number>([start, end]);
  for (const r of ranges) {
    bounds.add(r.start);
    bounds.add(r.end);
  }
  const points = [...bounds].filter((b) => b >= start && b <= end).sort((a, b) => a - b);

  const segments: Segment[] = [];
  for (let i = 0; i < points.length - 1; i += 1) {
    const a = points[i]!;
    const b = points[i + 1]!;
    if (b <= a) continue;
    const covering = ranges.filter((r) => r.start <= a && r.end >= b);
    segments.push({
      text: text.slice(a, b),
      flags: [...new Set(covering.map((r) => r.flag))],
      sids: [...new Set(covering.map((r) => r.sid))],
    });
  }
  return segments;
}

/** Which flags cite a given sentence, for the popover in the source view. */
export function flagsCiting(data: EvaluateResponse, sentenceId: string): string[] {
  return data.flags.filter((f) => f.evidence.some((e) => e.sentence_id === sentenceId)).map((f) => f.id);
}
