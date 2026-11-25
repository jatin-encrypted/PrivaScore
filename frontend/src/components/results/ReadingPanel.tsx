import type { Metrics } from "../../api/client";
import { copy } from "../../lib/copy";
import { num, percent } from "../../lib/format";

const CUE_LABELS: Record<string, string> = {
  conditionality: "Conditionality",
  generalization: "Generalization",
  modality: "Modality",
  numeric_quantifier: "Numeric quantifiers",
};

/**
 * Section 7.4 C7. Readability figures, then the vague-wording cues.
 *
 * A cue is a hint, not a verdict: the footnote says so, because "48% of sentences are vague"
 * would be a judgement the lexicon cannot support.
 */
export function ReadingPanel({ metrics }: { metrics: Metrics }) {
  const { readability: r, vagueness: v } = metrics;
  const maxCue = Math.max(1, ...Object.values(v.cues_per_1000_words));

  return (
    <section aria-labelledby="reading-heading">
      <h2 className="t-h2 border-t-2 border-rule-strong pt-8" id="reading-heading">
        {copy.results.readingHeading}
      </h2>

      <dl className="mt-6 grid grid-cols-2 gap-6 sm:grid-cols-4">
        <Figure label="Reading level" value={`Grade ${num(r.fk_grade)}`} note="US school grade (Flesch-Kincaid)" />
        <Figure label="Reading ease" value={num(r.flesch_reading_ease)} note="0-100, higher is easier" />
        <Figure label="Words" value={num(r.words)} note={`${num(r.avg_words_per_sentence)} per sentence`} />
        <Figure label="Minutes to read" value={num(r.reading_minutes)} note="at 238 words per minute" />
      </dl>

      <p className="t-body mt-8">
        <strong style={{ fontWeight: 700 }}>{percent(v.vague_sentence_fraction)}</strong>{" "}
        <span className="text-ink-2">of sentences contain a vague-wording cue.</span>
      </p>

      <ul className="mt-5 space-y-2">
        {Object.entries(v.cues_per_1000_words).map(([key, value]) => (
          <li key={key} className="grid grid-cols-[10rem_1fr_4rem] items-baseline gap-x-4">
            <span className="t-small text-ink-2">{CUE_LABELS[key] ?? key}</span>
            <span className="h-2 w-full" style={{ background: "var(--rule)" }}>
              <span
                className="block h-full"
                style={{ width: `${(value / maxCue) * 100}%`, background: "var(--ink-2)" }}
              />
            </span>
            <span className="t-small t-num text-right text-ink-2">{num(value)}</span>
          </li>
        ))}
      </ul>
      <p className="t-small mt-2 text-ink-3">per 1,000 words</p>

      {v.examples.length > 0 ? (
        <ul className="mt-8 space-y-4">
          {v.examples.slice(0, 3).map((e) => (
            <li key={e.sentence_id} className="border-l-2 border-rule pl-4">
              <p className="t-quote">{withCuesUnderlined(e.text, e.cues)}</p>
              <p className="t-code mt-1">{e.sentence_id}</p>
            </li>
          ))}
        </ul>
      ) : null}

      <p className="t-small mt-6 max-w-[68ch] text-ink-3">{copy.results.vagueNote}</p>
    </section>
  );
}

function Figure({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div>
      <dt className="t-small text-ink-2">{label}</dt>
      <dd className="t-num mt-1" style={{ fontStretch: "112%", fontWeight: 800, fontSize: "1.5rem" }}>
        {value}
      </dd>
      <p className="t-small text-ink-3">{note}</p>
    </div>
  );
}

/**
 * Gives each cue word a dotted underline. The cue strings come from the lexicon, so they are
 * matched case-insensitively against the sentence and rendered as text nodes; nothing is parsed
 * as markup.
 */
function withCuesUnderlined(text: string, cues: Record<string, string[]>) {
  const words = [...new Set(Object.values(cues).flat())].filter(Boolean);
  if (words.length === 0) return text;

  // Longest first, so "in some cases" wins over "some" where they overlap.
  const pattern = words
    .sort((a, b) => b.length - a.length)
    .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|");
  const parts = text.split(new RegExp(`(${pattern})`, "gi"));
  const lower = new Set(words.map((w) => w.toLowerCase()));

  return parts.map((part, i) =>
    lower.has(part.toLowerCase()) ? (
      <span key={i} style={{ textDecoration: "underline dotted", textUnderlineOffset: "3px" }}>
        {part}
      </span>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}
